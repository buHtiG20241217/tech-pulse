"""Ask page: grounded chat with source passages."""

from __future__ import annotations

import streamlit as st

from autosar_hld_assistant.app.rag.qa_engine import Answer, AnswerStatus
from autosar_hld_assistant.app.ui import state

SUGGESTIONS = (
    "Which software components are defined, and on which ECU?",
    "Which ports does BrakeControlSWC provide?",
    "What is the chain for functional flow FF-02?",
    "What happens in degraded mode?",
    "What is the battery warranty procedure?",  # out of scope: shows the refusal path
)

_STATUS_NOTES = {
    AnswerStatus.ANSWERED: (":green[**Answered**]", "from {n} passages"),
    AnswerStatus.NO_EVIDENCE: (":orange[**Not answered**]",
                               "nothing in the indexed documents is close enough to the question"),
    AnswerStatus.MODEL_DECLINED: (":orange[**Not answered**]", "the closest passages do not contain the answer"),
    AnswerStatus.NO_LLM: (":blue[**Retrieval only**]", "{n} passages found"),
    AnswerStatus.LLM_ERROR: (":red[**Error**]", "the language model request failed"),
}


def render() -> None:
    services = state.services()
    messages: list[dict] = st.session_state.setdefault("messages", [])

    title_col, clear_col = st.columns([5, 1], vertical_alignment="bottom")
    title_col.title("Ask")
    if clear_col.button("New conversation", disabled=not messages, width="stretch"):
        messages.clear()
        st.rerun()
    st.caption("Answers use only the indexed documents and cite document, page and section. "
               "If the documents don't cover a question, the assistant says so instead of guessing.")

    if services.store.count() == 0:
        st.info("No documents indexed yet. Index one on the Documents page first.")
        return

    if not messages:
        st.pills("Try one of these", SUGGESTIONS, key="suggestion", on_change=_take_suggestion)

    # Messages alternate question, answer; each pair is shown as one card.
    for question_msg, answer_msg in zip(messages[::2], messages[1::2]):
        with st.container(border=True):
            st.markdown(f"**{question_msg['content']}**")
            _render_answer(answer_msg["answer"])

    question = st.chat_input("Ask about SW-Cs, interfaces, ports, signals or flows")
    question = question or st.session_state.pop("pending_question", None)
    if question:
        _ask(question, messages)


def _take_suggestion() -> None:
    st.session_state["pending_question"] = st.session_state.get("suggestion")
    st.session_state["suggestion"] = None


def _ask(question: str, messages: list[dict]) -> None:
    history = [{"role": m["role"], "content": m["content"]} for m in messages]
    with st.container(border=True):
        st.markdown(f"**{question}**")
        with st.spinner("Searching the documents..."):
            answer = state.services().qa.answer_question(question, history=history, llm=state.llm())
    messages.append({"role": "user", "content": question})
    messages.append({"role": "assistant", "content": answer.text, "answer": answer})
    st.rerun()


def _render_answer(answer: Answer) -> None:
    if answer.status == AnswerStatus.LLM_ERROR:
        st.error(answer.text)
    else:
        st.markdown(answer.text)

    label, note = _STATUS_NOTES[answer.status]
    note = note.format(n=len(answer.citations))
    if answer.citations:
        note += f", evidence match: {answer.confidence.lower()}"
    st.caption(f"{label}: {note}")

    if answer.citations:
        with st.expander(f"Sources ({len(answer.citations)})"):
            for i, c in enumerate(answer.citations, start=1):
                st.markdown(f"**[{i}] {c.document_name}**, page {c.page_number} · {c.section_header}  "
                            f":gray[distance {c.distance:.2f}]")
                # PDF tables come out one cell per line; join them so a passage reads as a paragraph.
                st.code(" ".join(c.text.split()), language=None, wrap_lines=True)
