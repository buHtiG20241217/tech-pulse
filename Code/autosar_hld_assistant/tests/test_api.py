import pytest
from fastapi.testclient import TestClient

from autosar_hld_assistant.app import api
from autosar_hld_assistant.app.core.vector_store import FAISSVectorStore
from autosar_hld_assistant.app.rag.qa_engine import GroundedQAEngine
from autosar_hld_assistant.app.storage.db import DatabaseManager
from autosar_hld_assistant.app.storage.hitl_store import HITLReviewManager
from tests.helpers import EBC_PDF


@pytest.fixture
def client(tmp_path):
    services = api.Services.__new__(api.Services)
    services.store = FAISSVectorStore(index_path=str(tmp_path / "i.bin"), metadata_path=str(tmp_path / "m.json"))
    services.db = DatabaseManager(db_path=str(tmp_path / "t.db"))
    services.hitl = HITLReviewManager(services.db)
    services.qa = GroundedQAEngine(vector_store=services.store)
    api.app.dependency_overrides[api.services] = lambda: services
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


def _upload(client):
    with open(EBC_PDF, "rb") as f:
        return client.post("/documents", files={"file": ("ebc_brake_ecu_hld.pdf", f, "application/pdf")})


def test_upload_list_and_entities(client):
    response = _upload(client)
    assert response.status_code == 201 and response.json()["entity_counts"]["swcs"] == 4
    assert client.get("/documents").json()[0]["passages"] > 0
    assert len(client.get("/entities/ports").json()) == 6
    assert client.get("/entities/nonsense").status_code == 404


def test_non_pdf_upload_is_rejected(client):
    assert client.post("/documents", files={"file": ("notes.txt", b"hi", "text/plain")}).status_code == 415


def test_ask_without_llm_returns_passages(client):
    _upload(client)
    body = client.post("/ask", json={"question": "Which ports does ActuatorValves_SWC require?"}).json()
    assert body["status"] == "no_llm" and body["citations"] and body["confidence"] in ("High", "Medium", "Low")


def test_checks_review_and_delete(client):
    _upload(client)
    assert {f["check"] for f in client.get("/checks/ebc_brake_ecu_hld.pdf").json()} >= {"SW-C without ports"}
    swc_id = client.get("/entities/swcs").json()[0]["id"]
    bad = client.post("/reviews", json={"kind": "swcs", "entity_id": swc_id, "status": "Approved",
                                        "reviewer": "R", "rationale": ""})
    assert bad.status_code == 422
    ok = client.post("/reviews", json={"kind": "swcs", "entity_id": swc_id, "status": "Approved",
                                       "reviewer": "R", "rationale": "matches table"})
    assert ok.status_code == 201 and len(client.get("/reviews").json()) == 1
    assert client.delete("/documents/ebc_brake_ecu_hld.pdf").status_code == 204
    assert client.get("/checks/ebc_brake_ecu_hld.pdf").status_code == 404
