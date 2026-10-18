"""Reproducible evaluation of extraction, retrieval/grounding and (optionally) answers.

    python evaluation/run_evaluation.py            # offline parts only
    python evaluation/run_evaluation.py --llm      # also ask the configured LLM

Builds a fresh knowledge base from samples/ in a temporary folder (your data/
folder is not touched). Results go to the submission's Evaluation_Results/
folder, named per the submission convention, when the project sits in that
layout; otherwise to evaluation/results/ as evaluation_report.md and
evaluation_results.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT.parent))
os.environ.setdefault("AUTOSAR_DATA_DIR", tempfile.mkdtemp(prefix="autosar_eval_"))

from autosar_hld_assistant.app.analysis.compare import compare_documents  # noqa: E402
from autosar_hld_assistant.app.analysis.consistency import check_document  # noqa: E402
from autosar_hld_assistant.app.core.config import SIMILARITY_THRESHOLD  # noqa: E402
from autosar_hld_assistant.app.core.llm import LLMClient  # noqa: E402
from autosar_hld_assistant.app.core.vector_store import FAISSVectorStore  # noqa: E402
from autosar_hld_assistant.app.pipeline import ingest_pdf  # noqa: E402
from autosar_hld_assistant.app.rag.qa_engine import AnswerStatus, GroundedQAEngine  # noqa: E402
from autosar_hld_assistant.app.storage.db import DatabaseManager  # noqa: E402

SAMPLES = PROJECT / "samples"
DOCUMENTS = ["vbcs_brake_system_hld.pdf", "ebc_brake_ecu_hld.pdf", "ebc_brake_ecu_hld_v1_3.pdf"]
# Submission naming convention: <RegisterNo>_<Artifact>_v<Version>
SUBMISSION_JSON = "126003133_EvaluationResults_v1.0.json"
SUBMISSION_REPORT = "126003133_EvaluationReport_v1.0.md"
CITATION = re.compile(r"\[Doc:[^\]]*Page:\s*\d+", re.IGNORECASE)


def prf(predicted: set[str], truth: set[str]) -> dict:
    tp = len(predicted & truth)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(truth) if truth else 0.0
    return {"precision": round(precision, 3), "recall": round(recall, 3), "true_positives": tp,
            "predicted": len(predicted), "expected": len(truth),
            "missing": sorted(truth - predicted), "unexpected": sorted(predicted - truth)}


def evaluate_extraction(db: DatabaseManager, truth: dict) -> dict:
    results = {}
    for document, expected in truth.items():
        get = lambda kind: db.get_entities(kind, document)  # noqa: E731
        doc = {}
        for kind in ("swcs", "interfaces", "signals"):
            doc[kind] = prf({e["name"] for e in get(kind)}, set(expected[kind]))
        if "ports" in expected:
            doc["ports"] = prf({f"{p['swc_owner']}.{p['name']}" for p in get("ports")}, set(expected["ports"]))
        if "dependencies" in expected:
            doc["dependencies"] = prf({f"{d['source_swc']} -> {d['target_swc']}" for d in get("dependencies")},
                                      set(expected["dependencies"]))
        counts = {"ports": len(get("ports")), "dependencies": len(get("dependencies")),
                  "functional_flows": len(get("functional_flows")),
                  "provided_ports": sum(p["direction"] == "Provided" for p in get("ports"))}
        doc["counts"] = {k: {"expected": v, "extracted": counts[k], "match": v == counts[k]}
                         for k, v in expected.get("counts", {}).items()}
        results[document] = doc
    return results


def evaluate_retrieval(qa: GroundedQAEngine, questions: list[dict]) -> dict:
    rows = []
    for q in questions:
        hits = qa.retriever.retrieve(q["question"], top_k=qa.top_k)
        best = hits[0] if hits else None
        rows.append({"id": q["id"], "question": q["question"], "answerable": q["answerable"],
                     "best_distance": round(best[1], 3) if best else None,
                     "top_source": f"{best[0]['document_name']} p{best[0]['page_number']} {best[0]['section_header']}"
                     if best else None,
                     "passes_gate": bool(best and best[1] <= SIMILARITY_THRESHOLD)})

    sweep = []
    for t in [x / 100 for x in range(100, 165, 5)]:
        accepted = sum(r["answerable"] and r["best_distance"] <= t for r in rows)
        rejected = sum((not r["answerable"]) and r["best_distance"] > t for r in rows)
        sweep.append({"threshold": t, "answerable_passed": accepted, "unanswerable_blocked": rejected})
    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]
    return {
        "threshold": SIMILARITY_THRESHOLD,
        "questions": rows,
        "answerable_passing_gate": f"{sum(r['passes_gate'] for r in answerable)}/{len(answerable)}",
        "unanswerable_blocked_by_gate": f"{sum(not r['passes_gate'] for r in unanswerable)}/{len(unanswerable)}",
        "max_answerable_distance": max(r["best_distance"] for r in answerable),
        "min_unanswerable_distance": min(r["best_distance"] for r in unanswerable),
        "threshold_sweep": sweep,
    }


def evaluate_answers(qa: GroundedQAEngine, questions: list[dict], llm: LLMClient) -> dict:
    rows = []
    for q in questions:
        started = time.perf_counter()
        answer = qa.answer_question(q["question"], llm=llm)
        seconds = round(time.perf_counter() - started, 2)
        text = answer.text
        if q["answerable"]:
            found = [k for k in q["expect"] if k.lower() in text.lower()]
            correct = answer.status == AnswerStatus.ANSWERED and len(found) == len(q["expect"])
        else:
            found = []
            correct = answer.status in (AnswerStatus.NO_EVIDENCE, AnswerStatus.MODEL_DECLINED)
        rows.append({"id": q["id"], "question": q["question"], "answerable": q["answerable"],
                     "status": answer.status.value, "confidence": answer.confidence,
                     "has_inline_citation": bool(CITATION.search(text)),
                     "expected_terms_found": f"{len(found)}/{len(q.get('expect', []))}",
                     "correct": correct, "seconds": seconds, "answer": text})
    answered = [r for r in rows if r["status"] == "answered"]
    pos = [r for r in rows if r["answerable"]]
    neg = [r for r in rows if not r["answerable"]]
    return {
        "model": llm.describe(),
        "answerable_correct": f"{sum(r['correct'] for r in pos)}/{len(pos)}",
        "unanswerable_refused": f"{sum(r['correct'] for r in neg)}/{len(neg)}",
        "answers_with_citation": f"{sum(r['has_inline_citation'] for r in answered)}/{len(answered)}",
        "questions": rows,
    }


def write_report(results: dict, path: Path) -> None:
    lines = ["# Evaluation results", "", f"Run: {results['run_at']}  ", f"Threshold: {results['retrieval']['threshold']}", ""]
    lines += ["## Extraction", "", "| Document | Element | Precision | Recall | Missing | Unexpected |", "|---|---|---|---|---|---|"]
    for doc, kinds in results["extraction"].items():
        for kind, m in kinds.items():
            if kind == "counts":
                continue
            lines.append(f"| {doc} | {kind} | {m['precision']:.2f} | {m['recall']:.2f} | "
                         f"{', '.join(m['missing']) or '-'} | {', '.join(m['unexpected']) or '-'} |")
    lines += ["", "| Document | Count | Expected | Extracted | Match |", "|---|---|---|---|---|"]
    for doc, kinds in results["extraction"].items():
        for name, c in kinds["counts"].items():
            lines.append(f"| {doc} | {name} | {c['expected']} | {c['extracted']} | {'yes' if c['match'] else 'NO'} |")

    r = results["retrieval"]
    lines += ["", "## Retrieval and grounding gate", "",
              f"Answerable questions passing the gate: {r['answerable_passing_gate']}  ",
              f"Unanswerable questions blocked by the gate: {r['unanswerable_blocked_by_gate']}  ",
              f"Largest distance of an answerable question: {r['max_answerable_distance']}  ",
              f"Smallest distance of an unanswerable question: {r['min_unanswerable_distance']}", "",
              "| ID | Question | Answerable | Best distance | Top passage | Passes gate |", "|---|---|---|---|---|---|"]
    for q in r["questions"]:
        lines.append(f"| {q['id']} | {q['question']} | {'yes' if q['answerable'] else 'no'} | {q['best_distance']} | "
                     f"{q['top_source']} | {'yes' if q['passes_gate'] else 'no'} |")
    lines += ["", "| Threshold | Answerable passed | Unanswerable blocked |", "|---|---|---|"]
    lines += [f"| {s['threshold']:.2f} | {s['answerable_passed']} | {s['unanswerable_blocked']} |" for s in r["threshold_sweep"]]

    lines += ["", "## Consistency checks", ""]
    for doc, findings in results["consistency"].items():
        lines.append(f"**{doc}**: " + (f"{len(findings)} finding(s)" if findings else "no findings"))
        lines += [f"- {f['severity']}: {f['check']}: {f['element']}: {f['message']}" for f in findings]
        lines.append("")
    lines += ["## Revision comparison (EBC rev 1.2 → 1.3)", ""]
    for kind, d in results["comparison"].items():
        if d["added"] or d["removed"] or d["changed"]:
            changed = [f"{c['element']} {c['field']}: {c['old']} → {c['new']}" for c in d["changed"]]
            lines.append(f"- {kind}: added {d['added'] or '-'}, removed {d['removed'] or '-'}, changed {changed or '-'}")

    a = results.get("answers")
    lines += ["", "## End-to-end answers", ""]
    if not a:
        lines.append("Not run (no LLM configured, or run without --llm).")
    else:
        lines += [f"Model: {a['model']}  ", f"Answerable questions answered correctly: {a['answerable_correct']}  ",
                  f"Unanswerable questions refused: {a['unanswerable_refused']}  ",
                  f"Answers with an inline citation: {a['answers_with_citation']}", "",
                  "| ID | Status | Confidence | Expected terms | Citation | Correct | Seconds |", "|---|---|---|---|---|---|---|"]
        lines += [f"| {q['id']} | {q['status']} | {q['confidence']} | {q['expected_terms_found']} | "
                  f"{'yes' if q['has_inline_citation'] else 'no'} | {'yes' if q['correct'] else 'NO'} | {q['seconds']} |"
                  for q in a["questions"]]
        lines += ["", "### Answers", ""]
        for q in a["questions"]:
            lines += [f"**{q['id']}. {q['question']}**", "", q["answer"], ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--llm", action="store_true", help="also run end-to-end answers with the configured LLM")
    args = parser.parse_args()

    data_dir = Path(os.environ["AUTOSAR_DATA_DIR"])
    store = FAISSVectorStore(index_path=str(data_dir / "eval_index.bin"), metadata_path=str(data_dir / "eval_meta.json"))
    store.clear()
    db = DatabaseManager(db_path=str(data_dir / "eval.db"))
    db.clear_all(include_reviews=True)
    for name in DOCUMENTS:
        print(f"indexing {name}")
        ingest_pdf(SAMPLES / name, store, db)

    truth = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))
    questions = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    qa = GroundedQAEngine(vector_store=store)

    # Retrieval is evaluated on the main two documents only; rev 1.3 duplicates rev 1.2.
    store.remove_document("ebc_brake_ecu_hld_v1_3.pdf")

    results = {
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "extraction": evaluate_extraction(db, truth),
        "retrieval": evaluate_retrieval(qa, questions),
        "consistency": {name: [asdict(f) for f in check_document(db, name)] for name in DOCUMENTS},
        "comparison": {k: asdict(v) for k, v in
                       compare_documents(db, "ebc_brake_ecu_hld.pdf", "ebc_brake_ecu_hld_v1_3.pdf").items()},
    }
    llm = LLMClient()
    if args.llm:
        if llm.is_configured():
            print(f"asking {len(questions)} questions with {llm.describe()}")
            results["answers"] = evaluate_answers(qa, questions, llm)
        else:
            print("--llm given but no LLM is configured; skipping answers")

    submission_results = PROJECT.parent.parent / "Evaluation_Results"
    if submission_results.is_dir():
        out, json_name, report_name = submission_results, SUBMISSION_JSON, SUBMISSION_REPORT
    else:
        out, json_name, report_name = HERE / "results", "evaluation_results.json", "evaluation_report.md"
    out.mkdir(exist_ok=True)
    (out / json_name).write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_report(results, out / report_name)
    print(f"wrote {out / report_name}")


if __name__ == "__main__":
    main()
