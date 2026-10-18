from autosar_hld_assistant.app.ingestion.pdf_parser import PDFDocumentParser, clean_text, find_headings
from tests.helpers import EBC_PDF, VBCS_PDF


def test_heading_forms_are_recognised():
    text = "1. Introduction\n3.2 BrakeControlSWC\nSection 4. Signal Dictionary & CAN Bus Mapping"
    assert [h for _, h in find_headings(text)] == [
        "1 Introduction", "3.2 BrakeControlSWC", "4 Signal Dictionary & CAN Bus Mapping"]


def test_numbered_sentences_and_units_are_not_headings():
    text = ("2. Convert the raw values to float32 wheel speeds in km/h.\n"
            "10 ms\n"
            "1. Calculate BrakeCommand from WheelSpeed_FL, WheelSpeed_FR, WheelSpeed_RL, WheelSpeed_RR,")
    assert find_headings(text) == []


def test_heading_does_not_swallow_the_next_line():
    assert find_headings("3.3 WheelSpeedSensorSWC\nWheelSpeedSensorSWC acquires")[0][1] == "3.3 WheelSpeedSensorSWC"


def test_clean_text_drops_nulls_and_blank_lines():
    assert clean_text("  a\x00b  \n\n   \n c ") == "ab\nc"


def test_small_sample_pages_and_sections():
    parsed = PDFDocumentParser(str(EBC_PDF)).parse()
    assert parsed["document_name"] == "ebc_brake_ecu_hld.pdf"
    assert parsed["total_pages"] == 2
    headings = [h for page in parsed["pages"] for _, h in page["headings"]]
    assert "2 Software Component (SW-C) Definitions" in headings


def test_table_of_contents_page_is_not_used_for_sections():
    parsed = PDFDocumentParser(str(VBCS_PDF)).parse()
    assert parsed["total_pages"] == 24
    toc_pages = [p for p in parsed["pages"] if p["headings"] == [] and "4.4 Client-Server" in p["text"]]
    assert toc_pages, "expected the contents page to be recognised"
    page8 = parsed["pages"][7]
    assert any(h == "3.3 WheelSpeedSensorSWC" for _, h in page8["headings"])
