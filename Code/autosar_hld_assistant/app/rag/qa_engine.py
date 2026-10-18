"""Grounded question answering over the indexed HLD documents."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from autosar_hld_assistant.app.core.config import RETRIEVAL_TOP_K, SIMILARITY_THRESHOLD
from autosar_hld_assistant.app.core.llm import LLMClient, LLMError, LLMNotConfigured
from autosar_hld_assistant.app.core.vector_store import FAISSVectorStore
from autosar_hld_assistant.app.rag.retriever import CitationRetriever, Hit

NO_EVIDENCE_REPLY = (
    "The provided AUTOSAR HLD documents do not contain sufficient evidence to answer this question."
)

SYSTEM_PROMPT = f"""You answer questions about AUTOSAR High-Level Design (HLD) documents for automotive software engineers.

Rules:
1. Use only the information in the numbered passages under CONTEXT. Do not add facts from general knowledge.
2. Cite the passage behind each statement as [Doc: <name>, Page: <number>, Section: <section>].
3. Use earlier turns of the conversation only to work out what the question refers to.
4. Be concise. Prefer lists and tables when listing components, ports or signals.
5. If the passages do not contain the answer, reply with exactly this sentence and nothing else:
{NO_EVIDENCE_REPLY}"""

# Earlier turns sent with each question (user + assistant messages).
HISTORY_TURNS = 6

# Best-passage distance bands for the confidence label (see docs/evaluation.md).
CONFIDENCE_HIGH = 0.75
CONFIDENCE_MEDIUM = 0.95


_REFERS_BACK = re.compile(r"\b(it|its|they|them|their|those|these|that|this|one|ones|same)\b", re.IGNORECASE)
_NAMES_ELEMENT = re.compile(r"\b\w+_\w+\b|\b[A-Z][a-z]+[A-Z]\w*\b|\b[A-Z]{2,}-?\d+\b")


def is_follow_up(question: str) -> bool:
    """True if the question refers back to an earlier one and names no element itself.

    "Which interface does it use?" -> True; "Which ports does BrakeControlSWC
    provide?" -> False; "What is the battery warranty procedure?" -> False.
    """
    return bool(_REFERS_BACK.search(question)) and not _NAMES_ELEMENT.search(question)


class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    NO_EVIDENCE = "no_evidence"        # retrieval found nothing close enough; LLM not called
    MODEL_DECLINED = "model_declined"  # LLM saw the passages and said they don't answer it
    NO_LLM = "no_llm"                  # passages found, but no LLM configured
    LLM_ERROR = "llm_error"


@dataclass
class Citation:
    document_name: str
    page_number: int
    section_header: str
    chunk_id: str
    distance: float
    text: str


@dataclass
class Answer:
    question: str
    text: str
    status: AnswerStatus
    citations: list[Citation] = field(default_factory=list)

    @property
    def grounded(self) -> bool:
        return self.status == AnswerStatus.ANSWERED

    @property
    def confidence(self) -> str:
        """Retrieval confidence from the best passage's distance: High, Medium, Low or None.

        This rates how closely the evidence matches the question, not whether
        the generated text is correct.
        """
        if not self.citations:
            return "None"
        best = min(c.distance for c in self.citations)
        if best <= CONFIDENCE_HIGH:
            return "High"
        return "Medium" if best <= CONFIDENCE_MEDIUM else "Low"


def _citations(hits: list[Hit]) -> list[Citation]:
    return [
        Citation(
            document_name=meta.get("document_name", ""),
            page_number=meta.get("page_number", 0),
            section_header=meta.get("section_header", ""),
            chunk_id=meta.get("chunk_id", ""),
            distance=distance,
            text=meta.get("text", ""),
        )
        for meta, distance in hits
    ]


class GroundedQAEngine:
    """Retrieve, check the evidence is close enough, then ask the LLM.

    The distance check runs before the LLM is called, so questions the
    documents cannot answer never reach the model.
    """

    def __init__(
        self,
        retriever: CitationRetriever | None = None,
        vector_store: FAISSVectorStore | None = None,
        threshold: float = SIMILARITY_THRESHOLD,
        top_k: int = RETRIEVAL_TOP_K,
    ):
        self.retriever = retriever or CitationRetriever(vector_store=vector_store)
        self.threshold = threshold
        self.top_k = top_k

    def _supported(self, hits: list[Hit]) -> bool:
        return bool(hits) and hits[0][1] <= self.threshold

    def find_evidence(self, question: str, history: list[dict[str, str]] | None = None) -> list[Hit]:
        """Passages for `question`, or [] if none is close enough.

        A follow-up such as "and which ports does it use?" retrieves poorly on
        its own, so if the question alone fails, it is retried together with
        the previous user question.
        """
        hits = self.retriever.retrieve(question, top_k=self.top_k)
        if self._supported(hits):
            return hits
        previous = next((t["content"] for t in reversed(history or []) if t.get("role") == "user"), None)
        # Only a question that points back ("its ports", "those signals") is combined
        # with the previous one; an unrelated question must not borrow its evidence.
        if previous and is_follow_up(question):
            hits = self.retriever.retrieve(f"{previous}\n{question}", top_k=self.top_k)
            if self._supported(hits):
                return hits
        return []

    def answer_question(
        self,
        question: str,
        history: list[dict[str, str]] | None = None,
        llm: LLMClient | None = None,
    ) -> Answer:
        hits = self.find_evidence(question, history)
        if not hits:
            return Answer(question, NO_EVIDENCE_REPLY, AnswerStatus.NO_EVIDENCE)

        citations = _citations(hits)
        llm = llm or LLMClient()
        prompt = f"QUESTION: {question}\n\nCONTEXT:\n{self.retriever.format_context(hits)}"
        try:
            reply = llm.chat(SYSTEM_PROMPT, prompt, history=(history or [])[-HISTORY_TURNS:])
        except LLMNotConfigured:
            return Answer(question, "No language model is configured. The most relevant passages are listed below.",
                          AnswerStatus.NO_LLM, citations)
        except LLMError as exc:
            return Answer(question, f"The language model request failed: {exc}", AnswerStatus.LLM_ERROR, citations)

        if NO_EVIDENCE_REPLY in reply:
            return Answer(question, NO_EVIDENCE_REPLY, AnswerStatus.MODEL_DECLINED, citations)
        return Answer(question, reply.strip(), AnswerStatus.ANSWERED, citations)
