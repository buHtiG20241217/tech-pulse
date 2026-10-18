"""Documents page: index PDFs and see what the knowledge base holds."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from autosar_hld_assistant.app.pipeline import ingest_pdf, remove_document, save_upload
from autosar_hld_assistant.app.ui import state


def render() -> None:
    services = state.services()
    st.title("Documents")
    st.caption("Index AUTOSAR HLD PDFs. Embeddings are computed on this machine; only questions and "
               "the passages used to answer them are sent to the language model.")

    llm = state.llm()
    use_llm = st.toggle(
        "Refine extraction with the language model",
        value=llm.is_configured(),
        disabled=not llm.is_configured(),
        help="On by default when a model is configured. After the rule-based parsers, the model adds "
             "elements they missed and fills empty attributes; it never overrides values read from "
             "tables. Anything it adds is marked source = llm for review. Sends the first part of each "
             "document to the model.",
    )

    with st.container(border=True):
        st.markdown("**Upload PDFs**")
        files = st.file_uploader("PDF files", type="pdf", accept_multiple_files=True, label_visibility="collapsed")
        if st.button("Index uploaded files", type="primary", disabled=not files):
            for f in files:
                _ingest(save_upload(f.name, f.getvalue()), use_llm)

    st.markdown("**Or index a sample document**")
    for i, (col, sample) in enumerate(zip(st.columns(len(state.SAMPLES)), state.SAMPLES)):
        with col, st.container(border=True, height="stretch"):
            st.markdown(f"**{sample.title}**  \n:gray[{sample.summary}]")
            if st.button("Index", key=f"sample_{i}", width="stretch",
                         disabled=not sample.path.exists()):
                _ingest(sample.path, use_llm)

    _knowledge_base(services)


def _ingest(path: Path, use_llm: bool) -> None:
    services = state.services()
    with st.status(f"Indexing {path.name}", expanded=True) as status:
        try:
            with services.write_lock:
                result = ingest_pdf(path, services.store, services.db,
                                    llm=state.llm() if use_llm else None, progress=status.write)
        except ValueError as exc:
            status.update(label=f"{path.name}: {exc}", state="error")
            return
        counts = result.entity_counts
        summary = (f"{result.pages} pages, {result.chunks} passages, {counts.get('swcs', 0)} SW-Cs, "
                   f"{counts.get('interfaces', 0)} interfaces, {counts.get('ports', 0)} ports, "
                   f"{counts.get('signals', 0)} signals")
        verb = "Re-indexed" if result.replaced else "Indexed"
        status.update(label=f"{verb} {result.document_name}: {summary}", state="complete", expanded=False)


def _knowledge_base(services: state.Services) -> None:
    documents = services.db.list_documents()
    st.subheader("Knowledge base")
    if not documents:
        st.info("Nothing indexed yet. Upload an HLD or index one of the samples.")
        return

    totals = services.db.count_entities()
    metrics = [("Documents", len(documents)), ("Passages", services.store.count())]
    metrics += [(state.KIND_LABELS[k], totals[k]) for k in ("swcs", "interfaces", "ports", "signals")]
    for col, (label, value) in zip(st.columns(len(metrics)), metrics):
        col.metric(label, value, border=True)
    if "architecture" in state.PAGES:
        st.page_link(state.PAGES["architecture"], label="View the extracted elements on the Architecture page")

    chunk_counts = services.store.chunk_counts()
    rows = []
    for doc in documents:
        counts = services.db.count_entities(doc["document_name"])
        rows.append({
            "Document": doc["document_name"],
            "Pages": doc["total_pages"],
            "Passages": chunk_counts.get(doc["document_name"], 0),
            **{state.KIND_LABELS[k]: counts[k] for k in ("swcs", "interfaces", "ports", "signals")},
            "Indexed (UTC)": doc["created_at"],
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    with st.expander("Remove a document"):
        name = st.selectbox("Document", [d["document_name"] for d in documents], label_visibility="collapsed")
        st.caption("Removes its passages and extracted elements. Review history is kept.")
        if st.button("Remove", disabled=not name):
            with services.write_lock:
                remove_document(name, services.store, services.db)
            st.toast(f"Removed {name}.")
            st.rerun()
