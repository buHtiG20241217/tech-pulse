"""PDF text extraction with section-heading tracking."""

from __future__ import annotations

import os
import re
from typing import Any

from pypdf import PdfReader

# "3.2 BrakeControlSWC", "1. Introduction", "Section 4. Signal Dictionary"
_HEADING = re.compile(r"^(?:Section[ \t]+)?(\d{1,2}(?:\.\d{1,2})*)\.?[ \t]+([A-Z][^\n]{1,80})$", re.MULTILINE)
_MAX_HEADING_WORDS = 10
# A page listing this many headings is a table of contents, not content.
_TOC_HEADING_COUNT = 12

START_SECTION = "Front matter"


def find_headings(text: str) -> list[tuple[int, str]]:
    """Return (offset, heading) for each heading line in `text`.

    Numbered list items ("2. Convert the raw values to float32 ...") share the
    heading shape, so a heading must be short and must not end like a sentence.
    """
    headings = []
    for m in _HEADING.finditer(text):
        title = m.group(2).strip()
        if len(title.split()) > _MAX_HEADING_WORDS or title.endswith((".", ",", ";", ":")):
            continue
        headings.append((m.start(), f"{m.group(1)} {title}"))
    return headings


def clean_text(text: str) -> str:
    """Drop null bytes and blank lines, trim each line."""
    lines = (line.strip() for line in text.replace("\x00", "").splitlines())
    return "\n".join(line for line in lines if line)


class PDFDocumentParser:
    """Reads a text-based PDF page by page."""

    def __init__(self, file_path: str, document_name: str | None = None):
        self.file_path = file_path
        self.document_name = document_name or os.path.basename(file_path)

    def parse(self) -> dict[str, Any]:
        reader = PdfReader(self.file_path)
        pages: list[dict[str, Any]] = []
        full_text_parts: list[str] = []
        section = START_SECTION

        for page_number, page in enumerate(reader.pages, start=1):
            text = clean_text(page.extract_text() or "")
            headings = find_headings(text)
            is_contents = len(headings) >= _TOC_HEADING_COUNT
            if is_contents:
                headings = []

            pages.append({
                "page_number": page_number,
                "text": text,
                "section_at_start": "Table of contents" if is_contents else section,
                "headings": headings,
                "is_contents": is_contents,
            })
            full_text_parts.append(f"--- Page {page_number} ---\n{text}")
            if headings:
                section = headings[-1][1]

        return {
            "document_name": self.document_name,
            "file_path": self.file_path,
            "total_pages": len(reader.pages),
            "pages": pages,
            "full_text": "\n".join(full_text_parts),
        }
