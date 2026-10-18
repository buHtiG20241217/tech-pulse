"""Architecture page: browse extracted elements and the SW-C dependency graph."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd
import streamlit as st

from autosar_hld_assistant.app.analysis.consistency import ERROR, check_document
from autosar_hld_assistant.app.storage.db import ENTITY_TABLES
from autosar_hld_assistant.app.ui import state

ALL_DOCUMENTS = "All documents"


def dependency_dot(swcs: list[dict], dependencies: list[dict]) -> str:
    """Graphviz DOT for SW-Cs and their dependencies; parallel edges are merged."""
    edges: dict[tuple[str, str], set[str]] = defaultdict(set)
    for dep in dependencies:
        labels = edges[(dep["source_swc"], dep["target_swc"])]
        if dep.get("interface_name") not in (None, "", "unknown"):
            labels.add(dep["interface_name"])

    nodes = {s["name"] for s in swcs} | {n for pair in edges for n in pair}
    lines = [
        "digraph G {",
        '  graph [rankdir=LR, bgcolor="transparent", nodesep=0.5, ranksep=0.9];',
        '  node [shape=box, style="rounded,filled", fillcolor="#E8EEF9", color="#9AA8BF", '
        'fontname="Helvetica", fontsize=11, fontcolor="#1F2937"];',
        '  edge [color="#7A8699", fontname="Helvetica", fontsize=9, fontcolor="#7A8699"];',
    ]
    lines += [f'  "{n}";' for n in sorted(nodes)]
    for (src, tgt), interfaces in sorted(edges.items()):
        label = "\\n".join(sorted(interfaces))
        lines.append(f'  "{src}" -> "{tgt}" [label="{label}"];')
    lines.append("}")
    return "\n".join(lines)


def render() -> None:
    services = state.services()
    st.title("Architecture")
    st.caption("Elements extracted from the indexed documents. The source column shows how each was "
               "found: table (ID-numbered table row), regex (naming convention) or llm.")

    documents = [d["document_name"] for d in services.db.list_documents()]
    if not documents:
        st.info("No documents indexed yet.")
        return
    choice = st.selectbox("Document", [ALL_DOCUMENTS, *documents])
    document = None if choice == ALL_DOCUMENTS else choice

    data = {kind: services.db.get_entities(kind, document) for kind in ENTITY_TABLES}
    for col, kind in zip(st.columns(len(ENTITY_TABLES)), ENTITY_TABLES):
        col.metric(state.KIND_LABELS[kind], len(data[kind]), border=True)

    findings = [(name, f) for name in ([document] if document else documents) for f in check_document(services.db, name)]
    errors = sum(f.severity == ERROR for _, f in findings)
    checks_label = f"Checks ({errors} errors, {len(findings) - errors} other)" if findings else "Checks (none)"
    tabs = st.tabs(["Dependency graph", checks_label, *(state.KIND_LABELS[k] for k in ENTITY_TABLES)])
    with tabs[0]:
        if data["dependencies"]:
            st.graphviz_chart(dependency_dot(data["swcs"], data["dependencies"]), width="stretch")
            st.caption("Arrows follow the dependency as written in the document, labelled with the interface.")
        else:
            st.info("No dependencies extracted.")
    with tabs[1]:
        _checks(findings, show_document=document is None)

    for tab, kind in zip(tabs[2:], ENTITY_TABLES):
        with tab:
            _table(kind, data[kind], show_document=document is None)


def _checks(findings: list, show_document: bool) -> None:
    st.caption("Potential inconsistencies and gaps between the extracted tables. Each one needs an engineer "
               "to confirm it against the document; nothing is changed automatically.")
    if not findings:
        st.success("No inconsistencies found.")
        return
    rows = [{"Document": name, "Severity": f.severity, "Check": f.check, "Element": f.element,
             "Detail": f.message} for name, f in findings]
    columns = (["Document"] if show_document else []) + ["Severity", "Check", "Element", "Detail"]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_order=columns)


def _table(kind: str, rows: list[dict], show_document: bool) -> None:
    if not rows:
        st.info(f"No {state.KIND_LABELS[kind].lower()} extracted.")
        return
    spec = ENTITY_TABLES[kind]
    columns = list(spec.columns)
    if spec.reviewable:
        columns.append("review_status")
    columns.append("source")
    if show_document:
        columns.append("document_name")
    config = {c: st.column_config.TextColumn(c.replace("_", " ").capitalize()) for c in columns}
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_order=columns, column_config=config)
