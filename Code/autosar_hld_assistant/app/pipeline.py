"""Document ingestion: parse, chunk, index, extract, store.

Kept free of Streamlit so it can be tested and scripted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from autosar_hld_assistant.app.core.config import UPLOADS_DIR
from autosar_hld_assistant.app.core.llm import LLMClient
from autosar_hld_assistant.app.core.vector_store import FAISSVectorStore
from autosar_hld_assistant.app.extraction.autosar_extractor import AUTOSAREntityExtractor
from autosar_hld_assistant.app.ingestion.chunker import DocumentChunker
from autosar_hld_assistant.app.ingestion.pdf_parser import PDFDocumentParser
from autosar_hld_assistant.app.storage.db import DatabaseManager

Progress = Callable[[str], None]


@dataclass
class IngestResult:
    document_name: str
    pages: int
    chunks: int
    entity_counts: dict[str, int] = field(default_factory=dict)
    replaced: bool = False


def safe_filename(name: str) -> str:
    """Strip directories and characters that are unsafe in a file name."""
    stem = Path(name).name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", stem).strip(" .")
    return cleaned or "document.pdf"


def save_upload(name: str, data: bytes, uploads_dir: Path = UPLOADS_DIR) -> Path:
    uploads_dir.mkdir(parents=True, exist_ok=True)
    path = uploads_dir / safe_filename(name)
    path.write_bytes(data)
    return path


def ingest_pdf(
    path: str | Path,
    store: FAISSVectorStore,
    db: DatabaseManager,
    extractor: AUTOSAREntityExtractor | None = None,
    llm: LLMClient | None = None,
    progress: Progress = lambda _msg: None,
) -> IngestResult:
    """Index one PDF. Re-ingesting a document replaces its earlier data."""
    progress("Reading PDF text")
    parsed = PDFDocumentParser(str(path)).parse()
    name = parsed["document_name"]
    if not any(page["text"].strip() for page in parsed["pages"]):
        raise ValueError(f"No text found in {name}. Scanned PDFs need OCR first.")

    replaced = db.has_document(name)
    if replaced:
        progress("Removing the previous version")
        remove_document(name, store, db)

    progress("Splitting into passages and computing embeddings")
    chunks = DocumentChunker().create_chunks(parsed)
    store.add_chunks(chunks)

    progress("Extracting AUTOSAR elements" + (" (with LLM)" if llm and llm.is_configured() else ""))
    extracted = (extractor or AUTOSAREntityExtractor()).extract_all(parsed["full_text"], name, llm=llm)
    db.add_document(name, parsed["total_pages"], str(path))
    db.save_extracted_entities(extracted)

    counts = {kind: len(items) for kind, items in extracted.items() if isinstance(items, list)}
    return IngestResult(name, parsed["total_pages"], len(chunks), counts, replaced)


def remove_document(name: str, store: FAISSVectorStore, db: DatabaseManager) -> None:
    store.remove_document(name)
    db.delete_document(name)


def reset_knowledge_base(store: FAISSVectorStore, db: DatabaseManager, include_reviews: bool = False) -> None:
    store.clear()
    db.clear_all(include_reviews=include_reviews)
