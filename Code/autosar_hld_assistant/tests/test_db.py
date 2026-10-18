import sqlite3

import pytest

from autosar_hld_assistant.app.storage.db import DatabaseManager

EXTRACTED = {
    "document_name": "a.pdf",
    "swcs": [{"name": "WheelSpeedSensor_SWC", "type": "Sensor/Actuator", "source": "table"}],
    "interfaces": [{"name": "WheelSpeed_If"}],
    "ports": [{"name": "P_WheelSpeed", "direction": "Provided", "swc_owner": "WheelSpeedSensor_SWC"}],
    "signals": [{"name": "FL_WheelSpeed", "data_type": "float32", "unit": "km/h", "receiver_ports": ["X.RP_A"]}],
    "dependencies": [{"source_swc": "WheelSpeedSensor_SWC", "target_swc": "BrakeController_SWC"}],
    "functional_flows": [{"flow_name": "Flow 1", "sequence": "A -> B"}],
}


@pytest.fixture
def db(tmp_path):
    database = DatabaseManager(db_path=str(tmp_path / "t.db"))
    database.add_document("a.pdf", 2, "a.pdf")
    database.save_extracted_entities(EXTRACTED)
    return database


def test_entities_round_trip_with_defaults(db):
    swc = db.get_entities("swcs")[0]
    assert (swc["name"], swc["source"], swc["review_status"]) == ("WheelSpeedSensor_SWC", "table", "Pending")
    assert db.get_entities("interfaces")[0]["type"] == "Sender-Receiver"
    assert db.get_entities("dependencies")[0]["interface_name"] == ""
    assert db.count_entities() == {k: 1 for k in EXTRACTED if k != "document_name"}


def test_delete_document_removes_only_that_document(db):
    db.add_document("b.pdf", 1, "b.pdf")
    db.save_extracted_entities({**EXTRACTED, "document_name": "b.pdf"})
    db.delete_document("a.pdf")
    assert not db.has_document("a.pdf") and db.has_document("b.pdf")
    assert {s["document_name"] for s in db.get_entities("swcs")} == {"b.pdf"}


def test_only_editable_fields_can_be_updated(db):
    swc_id = db.get_entities("swcs")[0]["id"]
    db.update_entity("swcs", swc_id, {"description": "Acquires wheel pulses"})
    assert db.get_entity("swcs", swc_id)["description"] == "Acquires wheel pulses"
    with pytest.raises(ValueError):
        db.update_entity("swcs", swc_id, {"name": "Renamed"})


def test_clear_all_keeps_review_log_unless_asked(db):
    with db.connect() as conn:
        conn.execute("INSERT INTO hitl_reviews (entity_type, entity_name, status) VALUES ('SW-C', 'x', 'Approved')")
    db.clear_all()
    assert db.list_documents() == [] and db.get_entities("swcs") == []
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM hitl_reviews").fetchone()[0] == 1
    db.clear_all(include_reviews=True)
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM hitl_reviews").fetchone()[0] == 0


def test_databases_from_the_first_release_are_migrated(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE swc_entities (id INTEGER PRIMARY KEY, document_name TEXT, name TEXT, "
                     "type TEXT, description TEXT, review_status TEXT DEFAULT 'Pending')")
        conn.execute("CREATE TABLE hitl_reviews (id INTEGER PRIMARY KEY, entity_type TEXT, entity_name TEXT, "
                     "status TEXT, reviewer TEXT, rationale TEXT, risk_notes TEXT, updated_data TEXT, "
                     "created_at TIMESTAMP)")
    db = DatabaseManager(db_path=str(path))
    db.save_extracted_entities({"document_name": "a.pdf", "swcs": [{"name": "X_SWC", "source": "regex"}]})
    assert db.get_entities("swcs")[0]["source"] == "regex"
