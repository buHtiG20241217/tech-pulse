"""Generates the small synthetic EBC HLD samples used for demos and tests.

    python samples/generate_sample_pdf.py

writes two revisions of the same document:
- ebc_brake_ecu_hld.pdf       revision 1.2, internally consistent
- ebc_brake_ecu_hld_v1_3.pdf  revision 1.3, with deliberate changes and
  defects that the revision comparison and consistency checks should find
"""

from __future__ import annotations

import copy
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HERE = Path(__file__).resolve().parent

REV_1_2 = {
    "doc_id": "HLD-EBC-2026-V1.2",
    "swcs": [
        ["WheelSpeedSensor_SWC", "Sensor/Actuator",
         "Acquires raw pulse frequencies from 4 wheel speed sensors and converts them to speed."],
        ["BrakeController_SWC", "Application",
         "Executes slip ratio estimation and ABS brake pressure modulation algorithms."],
        ["ActuatorValves_SWC", "Sensor/Actuator", "Drives PWM hardware interfaces to hydraulic solenoid valves."],
        ["DiagnosticManager_SWC", "Service Component", "Monitors DTC event codes and reports safety bus faults."],
    ],
    "ports": [
        ["P_WheelSpeed", "Provided", "WheelSpeedSensor_SWC", "WheelSpeed_If"],
        ["R_WheelSpeed", "Required", "BrakeController_SWC", "WheelSpeed_If"],
        ["P_BrakeRequest", "Provided", "BrakeController_SWC", "BrakeRequest_If"],
        ["R_BrakeRequest", "Required", "ActuatorValves_SWC", "BrakeRequest_If"],
        ["P_ValveCmd", "Provided", "BrakeController_SWC", "ValveControl_If"],
        ["R_ValveCmd", "Required", "ActuatorValves_SWC", "ValveControl_If"],
    ],
    "signals": [
        ["FL_WheelSpeed", "float32", "km/h", "WheelSpeed_If", "Front Left Wheel velocity"],
        ["FR_WheelSpeed", "float32", "km/h", "WheelSpeed_If", "Front Right Wheel velocity"],
        ["RL_WheelSpeed", "float32", "km/h", "WheelSpeed_If", "Rear Left Wheel velocity"],
        ["RR_WheelSpeed", "float32", "km/h", "WheelSpeed_If", "Rear Right Wheel velocity"],
        ["BrakePressureCmd", "uint16", "kPa", "BrakeRequest_If", "Hydraulic pressure command"],
        ["ABS_ActiveFlag", "boolean", "-", "BrakeRequest_If", "Indicates active ABS slip control"],
    ],
    "dependencies": [
        ("WheelSpeedSensor_SWC", "BrakeController_SWC", "WheelSpeed_If"),
        ("BrakeController_SWC", "ActuatorValves_SWC", "ValveControl_If"),
        ("BrakeController_SWC", "DiagnosticManager_SWC", "DiagnosticReport_If"),
    ],
}


def revision_1_3() -> dict:
    rev = copy.deepcopy(REV_1_2)
    rev["doc_id"] = "HLD-EBC-2026-V1.3"
    # New component that nothing connects to yet (completeness finding).
    rev["swcs"].append(["HillHoldAssist_SWC", "Application", "Holds brake pressure on inclines until drive-off."])
    # ActuatorValves no longer consumes BrakeRequest_If (provided but unused).
    rev["ports"] = [p for p in rev["ports"] if p[0] != "R_BrakeRequest"]
    # Required interface that no SW-C provides (missing provider).
    rev["ports"].append(["R_VehicleSpeed", "Required", "HillHoldAssist_SWC", "VehicleSpeed_If"])
    # Changed signal attributes, and a new signal.
    rev["signals"][4] = ["BrakePressureCmd", "float32", "bar", "BrakeRequest_If", "Hydraulic pressure command"]
    rev["signals"].append(["VehicleSpeed", "float32", "km/h", "VehicleSpeed_If", "Reference vehicle speed"])
    # Dependency on a component that is not defined in Section 2.
    rev["dependencies"].append(("BrakeController_SWC", "ParkBrake_SWC", "ParkBrake_If"))
    return rev


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("DocTitle", parent=base["Title"], fontSize=20, leading=24,
                                textColor=colors.HexColor("#1E3A8A"), alignment=0),
        "h1": ParagraphStyle("H1", parent=base["Heading1"], fontSize=14, leading=18,
                             textColor=colors.HexColor("#1E40AF"), spaceBefore=12, spaceAfter=6),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], fontSize=11, leading=15,
                             textColor=colors.HexColor("#334155"), spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("Body", parent=base["Normal"], fontSize=9, leading=13,
                               textColor=colors.HexColor("#1E293B")),
    }


def _table(rows, widths, header_bg):
    table = Table(rows, colWidths=widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def build_sample_pdf(pdf_path: Path, rev: dict) -> None:
    s = _styles()
    story = [
        Paragraph("AUTOSAR High-Level Design (HLD) Specification", s["title"]),
        Paragraph(f"Document ID: {rev['doc_id']} | System: Electronic Brake Control (EBC) ECU", s["h2"]),
        Spacer(1, 10),
        Paragraph("Section 1. System Overview & Architecture Goals", s["h1"]),
        Paragraph(
            "This High-Level Design document specifies the AUTOSAR Classic Software Architecture for the Electronic "
            "Brake Control (EBC) ECU. The primary functional safety requirement is to acquire wheel speed signals, "
            "evaluate vehicle deceleration dynamics, execute Anti-Lock Braking System (ABS) algorithms, and command "
            "hydraulic actuator valves in real time.", s["body"]),
        Spacer(1, 10),
        Paragraph("Section 2. Software Component (SW-C) Definitions", s["h1"]),
        _table([["SW-C Name", "Component Type", "Description"], *rev["swcs"]], [130, 100, 270], "#DBEAFE"),
        Spacer(1, 15),
        Paragraph("Section 3. AUTOSAR Interfaces & Port Definitions", s["h1"]),
        Paragraph(
            "The components communicate using AUTOSAR Sender-Receiver and Client-Server interfaces. "
            "WheelSpeedSensor_SWC provides P_WheelSpeed using WheelSpeed_If. BrakeController_SWC requires "
            "R_WheelSpeed and provides P_BrakeRequest using BrakeRequest_If. ActuatorValves_SWC requires "
            "R_ValveCmd using ValveControl_If.", s["body"]),
        Spacer(1, 8),
        _table([["Port Name", "Direction", "SW-C Owner", "Interface Reference"], *rev["ports"]],
               [110, 80, 140, 170], "#E2E8F0"),
        PageBreak(),
        Paragraph("Section 4. Signal Dictionary & CAN Bus Mapping", s["h1"]),
        _table([["Signal Name", "Data Type", "Unit", "Interface Ref", "Description"], *rev["signals"]],
               [110, 60, 50, 110, 170], "#DCFCE7"),
        Spacer(1, 15),
        Paragraph("Section 5. Component Dependencies & Functional Flows", s["h1"]),
        Paragraph(
            "Component Dependencies: "
            + " ".join(f"- {a} -> {b} (via {i})" for a, b, i in rev["dependencies"])
            + "<br/><br/>Execution Flow: Flow: WheelSpeedSensor_SWC -> BrakeController_SWC -> ActuatorValves_SWC "
              "-> DiagnosticManager_SWC<br/><br/>"
              "Description of Flow: The physical sensor generates pulses acquired by WheelSpeedSensor_SWC. The speed "
              "data is transmitted over WheelSpeed_If to BrakeController_SWC, which determines slip control. Pressure "
              "actuation commands are sent over ValveControl_If to ActuatorValves_SWC, and diagnostic status is "
              "logged by DiagnosticManager_SWC.", s["body"]),
    ]
    SimpleDocTemplate(str(pdf_path), pagesize=letter, rightMargin=40, leftMargin=40,
                      topMargin=40, bottomMargin=40, title=rev["doc_id"]).build(story)


if __name__ == "__main__":
    for name, revision in (("ebc_brake_ecu_hld.pdf", REV_1_2), ("ebc_brake_ecu_hld_v1_3.pdf", revision_1_3())):
        build_sample_pdf(HERE / name, revision)
        print(f"wrote {HERE / name}")
