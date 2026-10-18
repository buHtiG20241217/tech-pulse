"""REST API over the same services the Streamlit UI uses.

    uvicorn autosar_hld_assistant.app.api:app --port 8000     (run from the parent folder)

Interactive documentation is served at /docs. The API is meant for local or
private-network use: it has no authentication.
"""

from __future__ import annotations

import threading
from dataclasses import asdict
from functools import lru_cache
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from pydantic import BaseModel, Field

from autosar_hld_assistant.app.analysis.compare import compare_documents
from autosar_hld_assistant.app.analysis.consistency import check_document
from autosar_hld_assistant.app.core.vector_store import FAISSVectorStore
from autosar_hld_assistant.app.pipeline import ingest_pdf, remove_document, save_upload
from autosar_hld_assistant.app.rag.qa_engine import GroundedQAEngine
from autosar_hld_assistant.app.storage.db import ENTITY_TABLES, DatabaseManager
from autosar_hld_assistant.app.storage.hitl_store import HITLReviewManager, ReviewError

app = FastAPI(title="AUTOSAR HLD Assistant API", version="1.0")
_write_lock = threading.Lock()


class Services:
    def __init__(self) -> None:
        self.store = FAISSVectorStore()
        self.db = DatabaseManager()
        self.hitl = HITLReviewManager(self.db)
        self.qa = GroundedQAEngine(vector_store=self.store)


@lru_cache(maxsize=1)
def services() -> Services:
    return Services()


class Question(BaseModel):
    question: str = Field(min_length=1)
    history: list[dict[str, str]] = []


class ReviewIn(BaseModel):
    kind: str
    entity_id: int
    status: str
    reviewer: str
    rationale: str
    risk_notes: str = ""
    corrections: dict[str, str] = {}


def _require_document(s: Services, name: str) -> None:
    if not s.db.has_document(name):
        raise HTTPException(404, f"Document '{name}' is not indexed.")


@app.get("/documents")
def list_documents(s: Services = Depends(services)) -> list[dict[str, Any]]:
    counts = s.store.chunk_counts()
    return [{**d, "passages": counts.get(d["document_name"], 0)} for d in s.db.list_documents()]


@app.post("/documents", status_code=201)
def upload_document(file: UploadFile, s: Services = Depends(services)) -> dict[str, Any]:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(415, "Only PDF files are accepted.")
    path = save_upload(file.filename, file.file.read())
    try:
        with _write_lock:
            result = ingest_pdf(path, s.store, s.db)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return asdict(result)


@app.delete("/documents/{name}", status_code=204)
def delete_document(name: str, s: Services = Depends(services)) -> None:
    _require_document(s, name)
    with _write_lock:
        remove_document(name, s.store, s.db)


@app.get("/entities/{kind}")
def get_entities(kind: str, document: str | None = None, s: Services = Depends(services)) -> list[dict[str, Any]]:
    if kind not in ENTITY_TABLES:
        raise HTTPException(404, f"Unknown kind. Use one of: {', '.join(ENTITY_TABLES)}.")
    return s.db.get_entities(kind, document)


@app.post("/ask")
def ask(body: Question, s: Services = Depends(services)) -> dict[str, Any]:
    answer = s.qa.answer_question(body.question, history=body.history)
    return {**asdict(answer), "status": answer.status.value, "grounded": answer.grounded,
            "confidence": answer.confidence}


@app.get("/checks/{name}")
def checks(name: str, s: Services = Depends(services)) -> list[dict[str, str]]:
    _require_document(s, name)
    return [asdict(f) for f in check_document(s.db, name)]


@app.get("/compare")
def compare(old: str, new: str, s: Services = Depends(services)) -> dict[str, Any]:
    _require_document(s, old)
    _require_document(s, new)
    return {kind: asdict(diff) for kind, diff in compare_documents(s.db, old, new).items()}


@app.post("/reviews", status_code=201)
def add_review(body: ReviewIn, s: Services = Depends(services)) -> dict[str, str]:
    try:
        s.hitl.log_review(body.kind, body.entity_id, body.status, reviewer=body.reviewer,
                          rationale=body.rationale, risk_notes=body.risk_notes, corrections=body.corrections)
    except ReviewError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"status": "recorded"}


@app.get("/reviews")
def reviews(s: Services = Depends(services)) -> list[dict[str, Any]]:
    return s.hitl.get_all_reviews()
