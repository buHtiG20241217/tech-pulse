"""Splits parsed pages into overlapping chunks that keep their citation data."""

from __future__ import annotations

from bisect import bisect_right
from typing import Any

from autosar_hld_assistant.app.core.config import CHUNK_OVERLAP, CHUNK_SIZE


def section_at(offset: int, page: dict[str, Any]) -> str:
    """Section heading in force at `offset` within the page."""
    headings = page.get("headings", [])
    i = bisect_right([pos for pos, _ in headings], offset)
    return headings[i - 1][1] if i else page.get("section_at_start", f"Page {page['page_number']}")


class DocumentChunker:
    """Fixed-size character windows, per page, so a chunk never spans two pages."""

    def __init__(self, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
        if not 0 <= chunk_overlap < chunk_size:
            raise ValueError("chunk_overlap must be at least 0 and smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def create_chunks(self, parsed_doc: dict[str, Any]) -> list[dict[str, Any]]:
        doc_name = parsed_doc["document_name"]
        step = self.chunk_size - self.chunk_overlap
        chunks: list[dict[str, Any]] = []

        for page in parsed_doc.get("pages", []):
            if page.get("is_contents"):
                continue  # a contents page only repeats headings and crowds out real passages
            text = page["text"]
            for start in range(0, max(len(text), 1), step):
                window = text[start:start + self.chunk_size]
                body = window.strip()
                if body:
                    # Label the chunk with the section covering its middle, so a
                    # heading just after the start wins over the previous one.
                    middle = start + len(window) // 2
                    chunks.append({
                        "chunk_id": f"{doc_name}_p{page['page_number']}_c{len(chunks) + 1}",
                        "document_name": doc_name,
                        "page_number": page["page_number"],
                        "section_header": section_at(middle, page),
                        "text": body,
                    })
                if start + self.chunk_size >= len(text):
                    break
        return chunks
