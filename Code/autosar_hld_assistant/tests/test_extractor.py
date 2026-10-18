from autosar_hld_assistant.app.extraction.autosar_extractor import (
    AUTOSAREntityExtractor,
    clean_llm_items,
    dedupe_flows,
    is_valid_signal,
    merge_entities,
    select_llm_input,
)
from autosar_hld_assistant.app.ingestion.pdf_parser import PDFDocumentParser
from tests.helpers import EBC_PDF, VBCS_PDF, FakeLLM


def _extract(pdf, llm=None):
    parsed = PDFDocumentParser(str(pdf)).parse()
    return AUTOSAREntityExtractor().extract_all(parsed["full_text"], parsed["document_name"], llm=llm)


def _names(items, field="name"):
    return sorted(i[field] for i in items)


def test_table_structured_hld_matches_its_own_summary_table():
    # VBCHLD-001, Table 49: 6 SW-Cs, 10 interfaces (7 S-R, 3 C-S), 29 ports
    # (10 provided, 19 required), 11 signals, 19 dependencies, 8 flows.
    result = _extract(VBCS_PDF)
    assert _names(result["swcs"]) == sorted([
        "BrakeControlSWC", "WheelSpeedSensorSWC", "BrakePressureSensorSWC", "BrakeActuatorSWC",
        "VehicleStateManagerSWC", "DiagnosticManagerSWC"])
    assert len(result["interfaces"]) == 10
    assert sum(i["type"] == "Client-Server" for i in result["interfaces"]) == 3
    assert len(result["ports"]) == 29
    assert sum(p["direction"] == "Provided" for p in result["ports"]) == 10
    assert len(result["signals"]) == 11
    assert len(result["dependencies"]) == 19
    assert len(result["functional_flows"]) == 8
    assert all(x["source"] == "table" for kind in ("ports", "signals", "dependencies") for x in result[kind])


def test_table_rows_carry_real_attributes():
    result = _extract(VBCS_PDF)
    wheel_fl = next(s for s in result["signals"] if s["name"] == "WheelSpeed_FL")
    assert (wheel_fl["data_type"], wheel_fl["unit"], wheel_fl["interface_ref"]) == ("float32", "km/h", "WheelSpeedIf")
    owners = {p["swc_owner"] for p in result["ports"] if p["name"] == "RP_DiagEvent"}
    assert len(owners) == 5  # same port name on five SW-Cs is kept apart
    ff02 = next(f for f in result["functional_flows"] if f["flow_id"] == "FF-02")
    assert "->" in ff02["sequence"]


def test_naming_convention_hld_without_tables():
    result = _extract(EBC_PDF)
    assert _names(result["swcs"]) == [
        "ActuatorValves_SWC", "BrakeController_SWC", "DiagnosticManager_SWC", "WheelSpeedSensor_SWC"]
    assert _names(result["interfaces"]) == [
        "BrakeRequest_If", "DiagnosticReport_If", "ValveControl_If", "WheelSpeed_If"]
    assert {(p["swc_owner"], p["name"]) for p in result["ports"]} >= {("ActuatorValves_SWC", "R_ValveCmd")}
    assert len(result["ports"]) == 6
    pressure = next(s for s in result["signals"] if s["name"] == "BrakePressureCmd")
    assert (pressure["data_type"], pressure["unit"]) == ("uint16", "kPa")  # read from the table, not guessed
    assert len(result["signals"]) == 6
    deps = {(d["source_swc"], d["target_swc"], d["interface_name"]) for d in result["dependencies"]}
    assert deps == {
        ("WheelSpeedSensor_SWC", "BrakeController_SWC", "WheelSpeed_If"),
        ("BrakeController_SWC", "ActuatorValves_SWC", "ValveControl_If"),
        ("BrakeController_SWC", "DiagnosticManager_SWC", "DiagnosticReport_If"),
    }  # the "Flow: A -> B -> C -> D" line must not add dependencies
    assert len(result["functional_flows"]) == 1


def test_basic_software_modules_and_ports_are_filtered():
    text = "CanIf PduR BrakeController_SWC uses WheelSpeed_If. PP_WheelSpeed GetWheelStatus EVT_Status"
    result = AUTOSAREntityExtractor().extract_all(text, "t.pdf")
    assert _names(result["interfaces"]) == ["WheelSpeed_If"]
    assert "PP_WheelSpeed" not in _names(result["signals"])
    assert not is_valid_signal("GetWheelStatus") and not is_valid_signal("EVT_Status")


def test_merge_fill_only_keeps_existing_values():
    base = [{"name": "A", "type": "Application", "description": ""}]
    extra = [{"name": "A", "type": "Sensor", "description": "from llm"}, {"name": "B", "type": "x"}, {"type": "no key"}]
    merged = {m["name"]: m for m in merge_entities(base, extra, ("name",), fill_only=True)}
    assert merged["A"] == {"name": "A", "type": "Application", "description": "from llm"}
    assert set(merged) == {"A", "B"}


def test_llm_cannot_add_to_or_override_a_table_defined_kind():
    llm = FakeLLM(json_reply={
        "swcs": [{"name": "BrakeControlSWC", "type": "Wrong"}, {"name": "ExtraSWC", "type": "Application"}],
        "interfaces": [{"name": "CanIf", "type": "Sender-Receiver"}],
    })
    result = _extract(VBCS_PDF, llm=llm)
    swcs = {s["name"]: s for s in result["swcs"]}
    assert swcs["BrakeControlSWC"]["type"] == "Application"
    assert "ExtraSWC" not in swcs  # the SW-C table is the complete list
    assert len(result["swcs"]) == 6
    assert "CanIf" not in _names(result["interfaces"])
    assert len(llm.calls) == 1


def test_llm_adds_marked_elements_where_the_document_has_no_table():
    text = "The brake function is split into a sensor component and a controller component."
    llm = FakeLLM(json_reply={
        "swcs": [{"name": "BrakeSensorSWC", "type": "Sensor/Actuator"}],
        "interfaces": [{"name": "CanIf"}, {"name": "BrakeDataIf", "type": "Sender-Receiver"}],
    })
    result = AUTOSAREntityExtractor().extract_all(text, "spec.pdf", llm=llm)
    assert [(s["name"], s["source"]) for s in result["swcs"]] == [("BrakeSensorSWC", "llm")]
    assert _names(result["interfaces"]) == ["BrakeDataIf"]  # BSW filter still applies


def test_merge_without_adding_keeps_only_known_items():
    base = [{"name": "A", "description": ""}]
    merged = merge_entities(base, [{"name": "A", "description": "x"}, {"name": "B"}], ("name",),
                            fill_only=True, add_new=False)
    assert merged == [{"name": "A", "description": "x"}]


def test_unconfigured_llm_is_not_called():
    llm = FakeLLM(configured=False)
    _extract(EBC_PDF, llm=llm)
    assert llm.calls == []


def test_llm_input_prefers_architecture_dense_pages_in_page_order():
    text = ("--- Page 1 ---\nTitle page and revision history\n"
            "--- Page 2 ---\nBrakeSWC uses WheelIf via RP_Wheel and PP_Brake\n"
            "--- Page 3 ---\nLegal notice\n"
            "--- Page 4 ---\nSensorSWC provides WheelIf\n")
    selected = select_llm_input(text, budget=90)
    assert "BrakeSWC" in selected and "SensorSWC" in selected
    assert "Title page" not in selected and "Legal" not in selected
    assert selected.index("BrakeSWC") < selected.index("SensorSWC")


def test_llm_items_are_cleaned():
    items = [
        {"name": "BrakeSWC", "type": "Application", "unexpected": "x"},
        {"name": "The brake controller component", "type": "Application"},  # a sentence, not a name
        "not a dict",
    ]
    assert clean_llm_items("swcs", items) == [{"name": "BrakeSWC", "type": "Application", "source": "llm"}]
    flows = [{"flow_name": "F1", "sequence": ["A_SWC", "B_SWC"]},
             {"flow_name": "F2", "sequence": ["A acquires data.", "B sends it."]}]
    assert clean_llm_items("functional_flows", flows) == [
        {"flow_name": "F1", "sequence": "A_SWC -> B_SWC", "source": "llm"}]
    assert clean_llm_items("swcs", "nonsense") == []


def test_duplicate_flow_sequences_are_kept_once():
    flows = [{"flow_name": "Flow 1", "sequence": "A -> B -> C"},
             {"flow_name": "Same chain", "sequence": "A->B ->C"},
             {"flow_name": "Other", "sequence": "A -> C"}]
    assert [f["flow_name"] for f in dedupe_flows(flows)] == ["Flow 1", "Other"]
