"""Sidebar: compact model status and settings, knowledge-base housekeeping."""

from __future__ import annotations

from dataclasses import replace

import streamlit as st

from autosar_hld_assistant.app.pipeline import reset_knowledge_base
from autosar_hld_assistant.app.ui import state

MISTRAL_MODELS = [
    "ministral-8b-latest",
    "mistral-small-latest",
    "mistral-medium-latest",
    "mistral-large-latest",
    "open-mistral-nemo",
]
PROVIDER_LABELS = {"mistral": "Mistral", "azure": "Azure OpenAI"}


def render() -> None:
    with st.sidebar:
        st.markdown("#### AUTOSAR HLD Assistant")
        st.caption("Grounded answers and architecture extraction for AUTOSAR design documents.")
        _model_section()
        _knowledge_base_section()


def _model_section() -> None:
    client = state.llm()
    if client.is_configured():
        st.badge(client.describe(), color="green")
    else:
        st.badge("No language model: retrieval only", color="orange")

    settings = state.llm_settings()
    with st.expander("Language model"):
        provider = st.segmented_control(
            "Provider", list(PROVIDER_LABELS), format_func=PROVIDER_LABELS.get,
            default=settings.provider if settings.provider in PROVIDER_LABELS else "mistral",
        ) or "mistral"
        if provider == "mistral":
            key = st.text_input("API key", value=settings.mistral_api_key, type="password")
            models = MISTRAL_MODELS if settings.mistral_model in MISTRAL_MODELS else [settings.mistral_model, *MISTRAL_MODELS]
            model = st.selectbox("Model", models, index=models.index(settings.mistral_model),
                                 accept_new_options=True, help="mistral-large needs a paid plan.")
            new = replace(settings, provider="mistral", mistral_api_key=key.strip(), mistral_model=model)
        else:
            endpoint = st.text_input("Endpoint", value=settings.azure_endpoint,
                                     placeholder="https://<resource>.openai.azure.com/")
            key = st.text_input("API key", value=settings.azure_api_key, type="password")
            deployment = st.text_input("Deployment", value=settings.azure_deployment)
            new = replace(settings, provider="azure", azure_endpoint=endpoint.strip(),
                          azure_api_key=key.strip(), azure_deployment=deployment.strip())

        if st.button("Apply", disabled=new == settings, width="stretch"):
            state.set_llm_settings(new)
            st.rerun()
        st.caption("For this browser session only; not saved to disk.")


def _knowledge_base_section() -> None:
    services = state.services()
    documents = services.db.list_documents()
    with st.expander(f"Knowledge base ({len(documents)} docs)"):
        st.caption(f"{services.store.count()} passages indexed")
        confirm = st.checkbox("Delete all indexed documents and extracted elements")
        include_reviews = st.checkbox("Also delete the review log", help="Kept by default as an audit record.")
        if st.button("Reset knowledge base", type="primary", disabled=not confirm, width="stretch"):
            with services.write_lock:
                reset_knowledge_base(services.store, services.db, include_reviews=include_reviews)
            st.session_state.pop("messages", None)
            st.toast("Knowledge base cleared.")
            st.rerun()
