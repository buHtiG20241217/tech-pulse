"""Shared services and per-session settings for the Streamlit views."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

import streamlit as st

from autosar_hld_assistant.app.core.config import SAMPLES_DIR, LLMSettings, llm_settings_from_env
from autosar_hld_assistant.app.core.llm import LLMClient
from autosar_hld_assistant.app.core.vector_store import FAISSVectorStore
from autosar_hld_assistant.app.rag.qa_engine import GroundedQAEngine
from autosar_hld_assistant.app.reports.exporter import ArchitectureReportExporter
from autosar_hld_assistant.app.storage.db import DatabaseManager
from autosar_hld_assistant.app.storage.hitl_store import HITLReviewManager

KIND_LABELS = {
    "swcs": "SW-Cs",
    "interfaces": "Interfaces",
    "ports": "Ports",
    "signals": "Signals",
    "dependencies": "Dependencies",
    "functional_flows": "Functional flows",
}


@dataclass(frozen=True)
class Sample:
    title: str
    summary: str
    path: Path


SAMPLES = (
    Sample("Vehicle Brake Control System HLD", "24 pages · ID-numbered tables · 6 SW-Cs, 29 ports",
           SAMPLES_DIR / "vbcs_brake_system_hld.pdf"),
    Sample("Electronic Brake Control ECU HLD, rev 1.2", "2 pages · plain tables · 4 SW-Cs",
           SAMPLES_DIR / "ebc_brake_ecu_hld.pdf"),
    Sample("Electronic Brake Control ECU HLD, rev 1.3", "Next revision, with changes and defects to find",
           SAMPLES_DIR / "ebc_brake_ecu_hld_v1_3.pdf"),
)


@dataclass
class Services:
    store: FAISSVectorStore
    db: DatabaseManager
    hitl: HITLReviewManager
    qa: GroundedQAEngine
    exporter: ArchitectureReportExporter
    # Serialises writes to the index and database across browser sessions.
    write_lock: threading.Lock = field(default_factory=threading.Lock)


@st.cache_resource(show_spinner="Loading the embedding model…")
def services() -> Services:
    store = FAISSVectorStore()
    store.embedder.embed_text("warm-up")  # load the model now rather than on the first question
    db = DatabaseManager()
    hitl = HITLReviewManager(db)
    return Services(store, db, hitl, GroundedQAEngine(vector_store=store), ArchitectureReportExporter(db, hitl))


# Navigation pages by url path, registered by main.py so views can link to each other.
PAGES: dict = {}

_SETTINGS_KEY = "llm_settings"


def llm_settings() -> LLMSettings:
    """LLM settings for this browser session (initialised from the environment)."""
    if _SETTINGS_KEY not in st.session_state:
        st.session_state[_SETTINGS_KEY] = llm_settings_from_env()
    return st.session_state[_SETTINGS_KEY]


def set_llm_settings(settings: LLMSettings) -> None:
    st.session_state[_SETTINGS_KEY] = settings


def llm() -> LLMClient:
    return LLMClient(llm_settings())
