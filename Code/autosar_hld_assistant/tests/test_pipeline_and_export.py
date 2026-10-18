import io
import json
import zipfile

import pytest

from autosar_hld_assistant.app.core.vector_store import FAISSVectorStore
from autosar_hld_assistant.app.pipeline import ingest_pdf, remove_document, safe_filename
from autosar_hld_assistant.app.reports.exporter import ArchitectureReportExporter
from autosar_hld_assistant.app.storage.db import DatabaseManager
from autosar_hld_assistant.app.storage.hitl_store import HITLReviewManager
from tests.helpers import EBC_PDF


@pytest.fixture
def kb(tmp_path):
    store = FAISSVectorStore(index_path=str(tmp_path / "i.bin"), metadata_path=str(tmp_path / "m.json"))
    return store, DatabaseManager(db_path=str(tmp_path / "t.db"))


def test_reingesting_replaces_instead_of_duplicating(kb):
    store, db = kb
    first = ingest_pdf(EBC_PDF, store, db)
    second = ingest_pdf(EBC_PDF, store, db)
    assert not first.replaced and second.replaced
    assert store.count() == first.chunks == second.chunks
    assert len(db.get_entities("swcs")) == first.entity_counts["swcs"] == 4


def test_remove_document_empties_index_and_tables(kb):
    store, db = kb
    ingest_pdf(EBC_PDF, store, db)
    remove_document("ebc_brake_ecu_hld.pdf", store, db)
    assert store.count() == 0 and db.list_documents() == [] and db.get_entities("ports") == []


@pytest.mark.parametrize("name, expected", [
    ("../../etc/passwd", "passwd"),
    ("C:\\Users\\x\\HLD v2.pdf", "HLD v2.pdf"),
    ("bad<>name?.pdf", "bad__name_.pdf"),
    ("...", "document.pdf"),
])
def test_safe_filename(name, expected):
    assert safe_filename(name) == expected


def test_exports_cover_every_table_and_the_review_log(kb):
    store, db = kb
    ingest_pdf(EBC_PDF, store, db)
    hitl = HITLReviewManager(db)
    swc = db.get_entities("swcs")[0]
    hitl.log_review("swcs", swc["id"], "Approved", reviewer="R", rationale="ok")
    exporter = ArchitectureReportExporter(db, hitl)

    markdown = exporter.generate_markdown_report()
    for heading in ("Software components", "Port interfaces", "Ports", "Signals", "Dependencies",
                    "Functional flows", "Review log"):
        assert heading in markdown
    assert "| Software components | 4 | 1 | 0 | 0 | 3 |" in markdown

    data = json.loads(exporter.generate_json_export())
    assert data["documents"][0]["document_name"] == "ebc_brake_ecu_hld.pdf"
    assert len(data["hitl_reviews"]) == 1

    names = zipfile.ZipFile(io.BytesIO(exporter.generate_csv_zip())).namelist()
    assert "functional_flows.csv" in names and "hitl_reviews.csv" in names
