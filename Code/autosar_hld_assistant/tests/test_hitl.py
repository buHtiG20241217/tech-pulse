import json

import pytest

from autosar_hld_assistant.app.storage.db import DatabaseManager
from autosar_hld_assistant.app.storage.hitl_store import HITLReviewManager, ReviewError


@pytest.fixture
def setup(tmp_path):
    db = DatabaseManager(db_path=str(tmp_path / "t.db"))
    db.save_extracted_entities({
        "document_name": "a.pdf",
        "swcs": [{"name": "BrakeControlSWC", "type": "Application", "description": ""}],
        "ports": [{"name": "RP_DiagEvent", "swc_owner": "BrakeControlSWC", "direction": "Required"},
                  {"name": "RP_DiagEvent", "swc_owner": "BrakeActuatorSWC", "direction": "Required"}],
    })
    return db, HITLReviewManager(db)


def _review(hitl, kind, entity_id, status="Approved", **kw):
    args = {"reviewer": "A. Engineer", "rationale": "Checked against Table 6", **kw}
    hitl.log_review(kind, entity_id, status, **args)


def test_approval_updates_status_and_logs(setup):
    db, hitl = setup
    swc = db.get_entities("swcs")[0]
    _review(hitl, "swcs", swc["id"], risk_notes="ASIL relevant")
    assert db.get_entity("swcs", swc["id"])["review_status"] == "Approved"
    log = hitl.get_all_reviews()[0]
    assert (log["entity_type"], log["entity_name"], log["status"], log["risk_notes"]) == \
        ("SW-C", "BrakeControlSWC", "Approved", "ASIL relevant")


def test_review_targets_one_port_even_when_names_repeat(setup):
    db, hitl = setup
    first, second = db.get_entities("ports")
    _review(hitl, "ports", second["id"], status="Rejected")
    assert db.get_entity("ports", first["id"])["review_status"] == "Pending"
    assert db.get_entity("ports", second["id"])["review_status"] == "Rejected"
    assert hitl.get_all_reviews()[0]["entity_name"] == "BrakeActuatorSWC.RP_DiagEvent"


def test_edit_applies_corrections_and_records_old_values(setup):
    db, hitl = setup
    swc = db.get_entities("swcs")[0]
    _review(hitl, "swcs", swc["id"], status="Edited",
            corrections={"description": "ABS slip control", "type": "Application"})
    assert db.get_entity("swcs", swc["id"])["description"] == "ABS slip control"
    changes = json.loads(hitl.get_all_reviews()[0]["updated_data"])
    assert changes == {"description": {"old": "", "new": "ABS slip control"}}


@pytest.mark.parametrize("kwargs, message", [
    ({"rationale": "  "}, "rationale"),
    ({"reviewer": ""}, "reviewer"),
    ({"status": "Edited"}, "Change at least one field"),
    ({"status": "Maybe"}, "Unknown status"),
])
def test_invalid_reviews_are_rejected(setup, kwargs, message):
    db, hitl = setup
    swc_id = db.get_entities("swcs")[0]["id"]
    status = kwargs.pop("status", "Approved")
    with pytest.raises(ReviewError, match=message):
        _review(hitl, "swcs", swc_id, status=status, **kwargs)
    assert hitl.get_all_reviews() == []


def test_dependencies_are_not_reviewable(setup):
    _, hitl = setup
    with pytest.raises(ReviewError):
        _review(hitl, "dependencies", 1)
