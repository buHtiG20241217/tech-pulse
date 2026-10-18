"""Review page: a lead engineer approves, rejects or corrects extracted elements."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from autosar_hld_assistant.app.storage.db import ENTITY_TABLES, REVIEW_STATUSES
from autosar_hld_assistant.app.storage.hitl_store import ReviewError, entity_label
from autosar_hld_assistant.app.ui import state

REVIEWABLE = [kind for kind, spec in ENTITY_TABLES.items() if spec.reviewable]
LOG_COLUMNS = ["created_at", "entity_type", "entity_name", "status", "reviewer", "rationale", "risk_notes",
               "updated_data"]


def render() -> None:
    services = state.services()
    st.title("Review")
    st.caption("Extracted elements start as Pending. A reviewer approves, rejects or corrects each one; "
               "every decision is logged with name, rationale and time.")

    feedback = st.session_state.pop("review_feedback", None)
    if feedback:
        st.toast(feedback)

    kind = st.segmented_control("Element type", REVIEWABLE, format_func=state.KIND_LABELS.get, default="swcs") or "swcs"
    entities = services.db.get_entities(kind)
    if not entities:
        st.info(f"No {state.KIND_LABELS[kind].lower()} to review. Index a document first.")
        _audit_log(services)
        return

    reviewed = sum(1 for e in entities if e.get("review_status") != "Pending")
    st.progress(reviewed / len(entities), text=f"{reviewed} of {len(entities)} reviewed")

    pending_only = st.toggle("Pending only", value=reviewed < len(entities))
    candidates = [e for e in entities if not pending_only or e.get("review_status") == "Pending"]
    if not candidates:
        st.success(f"All {state.KIND_LABELS[kind].lower()} have been reviewed.")
        _audit_log(services)
        return

    by_id = {e["id"]: e for e in candidates}
    entity_id = st.selectbox(
        "Element", list(by_id),
        format_func=lambda i: f"{entity_label(kind, by_id[i])}   ({by_id[i]['review_status']}, {by_id[i]['source']})",
    )
    _review_form(kind, by_id[entity_id])
    _audit_log(services)


def _review_form(kind: str, entity: dict) -> None:
    spec = ENTITY_TABLES[kind]
    with st.container(border=True):
        details = {c.replace("_", " ").capitalize(): entity.get(c) or "-" for c in spec.columns}
        details.update({"Found by": entity.get("source"), "Document": entity.get("document_name")})
        st.dataframe(pd.DataFrame([details]), hide_index=True, width="stretch")

        decision = st.segmented_control("Decision", REVIEW_STATUSES, key="review_decision")
        if decision == "Edited":
            st.markdown("**Corrections**")
            for field in spec.editable:
                st.text_input(field.replace("_", " ").capitalize(), value=entity.get(field) or "",
                              key=f"edit_{entity['id']}_{field}")

        st.text_input("Reviewer", key="review_reviewer")
        st.text_area("Rationale", key="review_rationale", placeholder="Why is this correct, wrong or changed?")
        st.text_area("Safety / risk notes (optional)", key="review_risk")
        st.button("Record decision", type="primary", disabled=decision is None,
                  on_click=_submit, args=(kind, entity["id"]))
        error = st.session_state.pop("review_error", None)
        if error:
            st.error(error)


def _submit(kind: str, entity_id: int) -> None:
    ss = st.session_state
    spec = ENTITY_TABLES[kind]
    corrections = {f: ss.get(f"edit_{entity_id}_{f}", "") for f in spec.editable}
    try:
        state.services().hitl.log_review(
            kind, entity_id, ss.get("review_decision"),
            reviewer=ss.get("review_reviewer", ""),
            rationale=ss.get("review_rationale", ""),
            risk_notes=ss.get("review_risk", ""),
            corrections=corrections,
        )
    except ReviewError as exc:
        ss["review_error"] = str(exc)
        return
    ss["review_feedback"] = f"Recorded: {ss['review_decision']}."
    for key in ("review_rationale", "review_risk", "review_decision"):
        ss[key] = None if key == "review_decision" else ""


def _audit_log(services: state.Services) -> None:
    st.subheader("Review log")
    reviews = services.hitl.get_all_reviews()
    if not reviews:
        st.caption("No decisions recorded yet.")
        return
    st.dataframe(pd.DataFrame(reviews), hide_index=True, width="stretch", column_order=LOG_COLUMNS,
                 column_config={c: c.replace("_", " ").capitalize() for c in LOG_COLUMNS})
