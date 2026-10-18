# Evaluation Results

| File | Contents |
|---|---|
| `126003133_EvaluationReport_v1.0.md` | Readable report: extraction precision/recall, retrieval distances and gate decisions, threshold sweep, consistency findings, revision comparison, and end-to-end answers when run with a model |
| `126003133_EvaluationResults_v1.0.json` | The same results, machine-readable |
| `126003133_EvaluationQuestions_v1.0.json` | 17 evaluation questions: 11 answerable (with expected terms) and 6 unanswerable (4 off-topic, 2 on-topic "hard negatives") |
| `126003133_GroundTruth_v1.0.json` | Expected elements per document. VBCS values come from the document's own Table 49 (page 24); EBC values from the generator script |
| `126003133_UnitTestResults_v1.0.txt` | Full pytest log (84 tests) |

## Reproduce

```powershell
cd ..\Code\autosar_hld_assistant
python evaluation\run_evaluation.py           # extraction, retrieval, checks, comparison (no API key needed)
$env:MISTRAL_API_KEY = "<key>"
python evaluation\run_evaluation.py --llm     # adds end-to-end answers from the model
python -m pytest -v > ..\..\Evaluation_Results\126003133_UnitTestResults_v1.0.txt
```

The script builds a fresh knowledge base from `samples/` in a temporary folder and writes its
results to this folder.

## Metrics

| Metric | Definition |
|---|---|
| Extraction precision / recall | Per element type, extracted names compared with the ground-truth names |
| Gate pass rate | Share of answerable questions whose best passage is within the threshold |
| Gate block rate | Share of unanswerable questions stopped before the LLM |
| Answer correctness (with `--llm`) | Answerable: status *answered* **and** all expected terms present. Unanswerable: status *no_evidence* or *model_declined* |
| Citation rate (with `--llm`) | Answered replies containing at least one `[Doc: …, Page: …]` tag |
