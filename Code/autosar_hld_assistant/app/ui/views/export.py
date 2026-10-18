"""Export page: download the architecture report."""

from __future__ import annotations

import streamlit as st

from autosar_hld_assistant.app.ui import state


def render() -> None:
    exporter = state.services().exporter
    st.title("Export")
    st.caption("The extracted architecture with review status and the full review log.")

    markdown = exporter.generate_markdown_report()
    md_col, json_col, csv_col = st.columns(3)
    md_col.download_button("Markdown report", markdown, "autosar_architecture_report.md", "text/markdown", width="stretch")
    json_col.download_button("JSON export", exporter.generate_json_export(), "autosar_architecture.json",
                             "application/json", width="stretch")
    csv_col.download_button("CSV tables (zip)", exporter.generate_csv_zip(), "autosar_architecture_csv.zip",
                            "application/zip", width="stretch")

    st.subheader("Preview")
    with st.container(border=True, height=640):
        st.markdown(markdown)
