import pytest

from autosar_hld_assistant.app.analysis.compare import compare_documents, compare_rows
from autosar_hld_assistant.app.analysis.consistency import ERROR, WARNING, check_architecture, check_document
from autosar_hld_assistant.app.core.vector_store import FAISSVectorStore
from autosar_hld_assistant.app.pipeline import ingest_pdf
from autosar_hld_assistant.app.storage.db import DatabaseManager
from tests.helpers import EBC_PDF, EBC_V13_PDF, VBCS_PDF


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("kb")
    store = FAISSVectorStore(index_path=str(tmp / "i.bin"), metadata_path=str(tmp / "m.json"))
    db = DatabaseManager(db_path=str(tmp / "t.db"))
    for pdf in (VBCS_PDF, EBC_PDF, EBC_V13_PDF):
        ingest_pdf(pdf, store, db)
    return db


def _checks(findings):
    return {(f.severity, f.check, f.element) for f in findings}


def test_consistent_document_has_no_findings(kb):
    assert check_document(kb, "vbcs_brake_system_hld.pdf") == []


def test_planted_defects_in_revision_1_3_are_found(kb):
    found = _checks(check_document(kb, "ebc_brake_ecu_hld_v1_3.pdf"))
    assert (ERROR, "Missing provider", "VehicleSpeed_If") in found
    assert (ERROR, "Undefined SW-C", "BrakeController_SWC -> ParkBrake_SWC") in found
    assert (WARNING, "Unused interface", "BrakeRequest_If") in found
    assert (WARNING, "SW-C without ports", "DiagnosticManager_SWC") in found


def test_client_server_dependencies_may_run_client_to_server():
    data = {
        "swcs": [{"name": "ClientSWC"}, {"name": "ServerSWC"}],
        "interfaces": [{"name": "SvcIf"}],
        "ports": [{"name": "RP_Svc", "direction": "Required", "swc_owner": "ClientSWC", "interface_ref": "SvcIf"},
                  {"name": "PP_Svc", "direction": "Provided", "swc_owner": "ServerSWC", "interface_ref": "SvcIf"}],
        "dependencies": [{"source_swc": "ClientSWC", "target_swc": "ServerSWC", "interface_name": "SvcIf"}],
    }
    assert check_architecture(data) == []


def test_checks_needing_port_owners_are_skipped_without_them():
    data = {"swcs": [{"name": "A_SWC"}], "ports": [{"name": "P_X", "direction": "Provided", "swc_owner": "unknown",
                                                    "interface_ref": "X_If"}]}
    assert check_architecture(data) == []


def test_revision_comparison(kb):
    diff = compare_documents(kb, "ebc_brake_ecu_hld.pdf", "ebc_brake_ecu_hld_v1_3.pdf")
    assert diff["swcs"].added == ["HillHoldAssist_SWC"]
    assert diff["ports"].removed == ["ActuatorValves_SWC.R_BrakeRequest"]
    assert diff["ports"].added == ["HillHoldAssist_SWC.R_VehicleSpeed"]
    changes = {(c.element, c.field, c.old, c.new) for c in diff["signals"].changed}
    assert changes == {("BrakePressureCmd", "data_type", "uint16", "float32"), ("BrakePressureCmd", "unit", "kPa", "bar")}
    assert diff["functional_flows"].is_empty


def test_identical_rows_have_no_diff():
    rows = [{"name": "A", "type": "Application", "description": "x"}]
    assert compare_rows("swcs", rows, rows).is_empty
