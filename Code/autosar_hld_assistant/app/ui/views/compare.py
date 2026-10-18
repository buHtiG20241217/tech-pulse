"""Compare page: differences between two revisions of an HLD."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from autosar_hld_assistant.app.analysis.compare import compare_documents
from autosar_hld_assistant.app.ui import state


def render() -> None:
    services = state.services()
    st.title("Compare")
    st.caption("What was added, removed or changed between two indexed documents, element by element. "
               "Index both revisions on the Documents page first.")

    documents = [d["document_name"] for d in services.db.list_documents()]
    if len(documents) < 2:
        st.info("Index at least two documents to compare them. The samples include two revisions of the EBC HLD.")
        return

    old_col, new_col = st.columns(2)
    old = old_col.selectbox("Older revision", documents, index=max(len(documents) - 2, 0))
    new = new_col.selectbox("Newer revision", documents, index=len(documents) - 1)
    if old == new:
        st.warning("Choose two different documents.")
        return

    diff = compare_documents(services.db, old, new)
    summary = [{"Element": state.KIND_LABELS[k], "Added": len(d.added), "Removed": len(d.removed),
                "Changed": len(d.changed)} for k, d in diff.items()]
    st.dataframe(pd.DataFrame(summary), hide_index=True, width="stretch")

    if all(d.is_empty for d in diff.values()):
        st.success("No differences in the extracted architecture.")
        return

    for kind, d in diff.items():
        if d.is_empty:
            continue
        with st.container(border=True):
            st.markdown(f"**{state.KIND_LABELS[kind]}**")
            for name in d.added:
                st.markdown(f":green[**Added**] `{name}`")
            for name in d.removed:
                st.markdown(f":red[**Removed**] `{name}`")
            for c in d.changed:
                st.markdown(f":orange[**Changed**] `{c.element}` {c.field.replace('_', ' ')}: "
                            f"`{c.old or '-'}` → `{c.new or '-'}`")
