"""Retrieval with citation metadata, and formatting of passages for the prompt."""

from __future__ import annotations

from typing import Any

from autosar_hld_assistant.app.core.vector_store import FAISSVectorStore

Hit = tuple[dict[str, Any], float]


class CitationRetriever:

    def __init__(self, vector_store: FAISSVectorStore | None = None):
        self.vector_store = vector_store or FAISSVectorStore()

    def retrieve(self, query: str, top_k: int = 5) -> list[Hit]:
        return self.vector_store.search(query, top_k=top_k)

    @staticmethod
    def format_context(hits: list[Hit]) -> str:
        """Numbered passages with source labels, as placed in the LLM prompt."""
        blocks = []
        for i, (meta, _distance) in enumerate(hits, start=1):
            label = (f"[{i}] Doc: {meta.get('document_name', '?')}, Page: {meta.get('page_number', '?')}, "
                     f"Section: {meta.get('section_header', '?')}")
            blocks.append(f"{label}\n{meta.get('text', '')}")
        return "\n\n---\n\n".join(blocks)
