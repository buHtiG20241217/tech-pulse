"""Streamlit entry point. From the project folder: streamlit run app/main.py"""

import sys
from pathlib import Path

# Imports are rooted at the folder that contains `autosar_hld_assistant`.
_PROJECT_PARENT = Path(__file__).resolve().parents[2]
if str(_PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_PARENT))

import streamlit as st  # noqa: E402

from autosar_hld_assistant.app.core.embeddings import EmbeddingModelUnavailable  # noqa: E402
from autosar_hld_assistant.app.ui import sidebar, state  # noqa: E402
from autosar_hld_assistant.app.ui.views import architecture, ask, compare, documents, export, review  # noqa: E402

st.set_page_config(page_title="AUTOSAR HLD Assistant", layout="wide")

try:
    state.services()
except EmbeddingModelUnavailable as exc:
    st.error(str(exc))
    st.stop()

pages = [
    st.Page(documents.render, title="Documents", default=True),
    st.Page(ask.render, title="Ask", url_path="ask"),
    st.Page(architecture.render, title="Architecture", url_path="architecture"),
    st.Page(compare.render, title="Compare", url_path="compare"),
    st.Page(review.render, title="Review", url_path="review"),
    st.Page(export.render, title="Export", url_path="export"),
]
state.PAGES.update({p.url_path: p for p in pages})
page = st.navigation(pages, position="top")
page.run()
# After the page, so the sidebar counts include anything the page just indexed.
sidebar.render()
