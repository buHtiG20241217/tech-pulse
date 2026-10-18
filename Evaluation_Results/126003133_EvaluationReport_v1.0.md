# Evaluation results

Run: 2026-10-13 14:40 UTC  
Threshold: 1.1

## Extraction

| Document | Element | Precision | Recall | Missing | Unexpected |
|---|---|---|---|---|---|
| vbcs_brake_system_hld.pdf | swcs | 1.00 | 1.00 | - | - |
| vbcs_brake_system_hld.pdf | interfaces | 1.00 | 1.00 | - | - |
| vbcs_brake_system_hld.pdf | signals | 1.00 | 1.00 | - | - |
| ebc_brake_ecu_hld.pdf | swcs | 1.00 | 1.00 | - | - |
| ebc_brake_ecu_hld.pdf | interfaces | 1.00 | 1.00 | - | - |
| ebc_brake_ecu_hld.pdf | signals | 1.00 | 1.00 | - | - |
| ebc_brake_ecu_hld.pdf | ports | 1.00 | 1.00 | - | - |
| ebc_brake_ecu_hld.pdf | dependencies | 1.00 | 1.00 | - | - |

| Document | Count | Expected | Extracted | Match |
|---|---|---|---|---|
| vbcs_brake_system_hld.pdf | ports | 29 | 29 | yes |
| vbcs_brake_system_hld.pdf | provided_ports | 10 | 10 | yes |
| vbcs_brake_system_hld.pdf | dependencies | 19 | 19 | yes |
| vbcs_brake_system_hld.pdf | functional_flows | 8 | 8 | yes |
| ebc_brake_ecu_hld.pdf | functional_flows | 1 | 1 | yes |

## Retrieval and grounding gate

Answerable questions passing the gate: 11/11  
Unanswerable questions blocked by the gate: 5/6  
Largest distance of an answerable question: 1.046  
Smallest distance of an unanswerable question: 0.514

| ID | Question | Answerable | Best distance | Top passage | Passes gate |
|---|---|---|---|---|---|
| Q01 | Which software components are defined in the brake control system? | yes | 0.679 | vbcs_brake_system_hld.pdf p5 1.3 Definitions and Abbreviations | yes |
| Q02 | Which ports does BrakeControlSWC provide? | yes | 0.508 | vbcs_brake_system_hld.pdf p8 3.2 BrakeControlSWC | yes |
| Q03 | Which signals are carried by WheelSpeedIf? | yes | 0.775 | vbcs_brake_system_hld.pdf p15 6.2 Signal Definitions | yes |
| Q04 | What is the chain for functional flow FF-02? | yes | 0.946 | vbcs_brake_system_hld.pdf p18 8.2 FF-01 Primary Braking Flow | yes |
| Q05 | What does BrakeControlSWC do in degraded mode? | yes | 0.721 | vbcs_brake_system_hld.pdf p24 12.1 Summary of Architecture Elements | yes |
| Q06 | On which ECU is DiagnosticManagerSWC deployed? | yes | 0.882 | vbcs_brake_system_hld.pdf p6 2.2 ECU Deployment | yes |
| Q07 | Which interfaces are Client-Server interfaces? | yes | 1.046 | vbcs_brake_system_hld.pdf p8 3.2 BrakeControlSWC | yes |
| Q08 | Which CAN message broadcasts ABS_Active? | yes | 0.929 | vbcs_brake_system_hld.pdf p15 6.2 Signal Definitions | yes |
| Q09 | When does DiagnosticManagerSWC run the actuator self-test? | yes | 0.654 | vbcs_brake_system_hld.pdf p23 10.4 Diagnostic Self-Test | yes |
| Q10 | Which port does ActuatorValves_SWC use to receive the valve command? | yes | 0.898 | ebc_brake_ecu_hld.pdf p1 3 AUTOSAR Interfaces & Port Definitions | yes |
| Q11 | What data type and unit does BrakePressureCmd have in the EBC design? | yes | 0.84 | ebc_brake_ecu_hld.pdf p1 1 System Overview & Architecture Goals | yes |
| N01 | What is the vehicle battery warranty replacement procedure? | no | 1.63 | vbcs_brake_system_hld.pdf p11 3.7 DiagnosticManagerSWC | no |
| N02 | What is the capital of France? | no | 1.847 | vbcs_brake_system_hld.pdf p17 7.3 Signal Layout | no |
| N03 | How do I bake sourdough bread? | no | 1.578 | vbcs_brake_system_hld.pdf p17 7.3 Signal Layout | no |
| N04 | How do I sort a list in Python? | no | 1.989 | vbcs_brake_system_hld.pdf p18 8.1 Flow Overview | no |
| N05 | Which ASIL is assigned to BrakeControlSWC? | no | 0.514 | vbcs_brake_system_hld.pdf p8 3.2 BrakeControlSWC | yes |
| N06 | What is the tyre pressure warning threshold? | no | 1.156 | vbcs_brake_system_hld.pdf p22 10.2 Diagnostic Events | no |

| Threshold | Answerable passed | Unanswerable blocked |
|---|---|---|
| 1.00 | 10 | 5 |
| 1.05 | 11 | 5 |
| 1.10 | 11 | 5 |
| 1.15 | 11 | 5 |
| 1.20 | 11 | 4 |
| 1.25 | 11 | 4 |
| 1.30 | 11 | 4 |
| 1.35 | 11 | 4 |
| 1.40 | 11 | 4 |
| 1.45 | 11 | 4 |
| 1.50 | 11 | 4 |
| 1.55 | 11 | 4 |
| 1.60 | 11 | 3 |

## Consistency checks

**vbcs_brake_system_hld.pdf**: no findings

**ebc_brake_ecu_hld.pdf**: 2 finding(s)
- Warning: Dependency not backed by ports: BrakeController_SWC -> DiagnosticManager_SWC: No matching provided/required port pair on DiagnosticReport_If.
- Warning: SW-C without ports: DiagnosticManager_SWC: No port of this SW-C is listed in the port table.

**ebc_brake_ecu_hld_v1_3.pdf**: 6 finding(s)
- Error: Missing provider: VehicleSpeed_If: Required by HillHoldAssist_SWC, but no SW-C provides it.
- Error: Undefined SW-C: BrakeController_SWC -> ParkBrake_SWC: ParkBrake_SWC is not defined as a SW-C.
- Warning: Dependency not backed by ports: BrakeController_SWC -> DiagnosticManager_SWC: No matching provided/required port pair on DiagnosticReport_If.
- Warning: Dependency not backed by ports: BrakeController_SWC -> ParkBrake_SWC: No matching provided/required port pair on ParkBrake_If.
- Warning: SW-C without ports: DiagnosticManager_SWC: No port of this SW-C is listed in the port table.
- Warning: Unused interface: BrakeRequest_If: Provided by BrakeController_SWC, but no SW-C requires it.

## Revision comparison (EBC rev 1.2 → 1.3)

- swcs: added ['HillHoldAssist_SWC'], removed -, changed -
- interfaces: added ['ParkBrake_If', 'VehicleSpeed_If'], removed -, changed -
- ports: added ['HillHoldAssist_SWC.R_VehicleSpeed'], removed ['ActuatorValves_SWC.R_BrakeRequest'], changed -
- signals: added ['VehicleSpeed'], removed -, changed ['BrakePressureCmd data_type: uint16 → float32', 'BrakePressureCmd unit: kPa → bar']
- dependencies: added ['BrakeController_SWC -> ParkBrake_SWC -> ParkBrake_If'], removed -, changed -

## End-to-end answers

Model: Mistral · ministral-8b-latest  
Answerable questions answered correctly: 10/11  
Unanswerable questions refused: 6/6  
Answers with an inline citation: 10/10

| ID | Status | Confidence | Expected terms | Citation | Correct | Seconds |
|---|---|---|---|---|---|---|
| Q01 | answered | High | 3/3 | yes | yes | 2.52 |
| Q02 | answered | High | 2/2 | yes | yes | 1.27 |
| Q03 | answered | Medium | 2/2 | yes | yes | 1.17 |
| Q04 | answered | Medium | 2/2 | yes | yes | 1.07 |
| Q05 | answered | High | 2/2 | yes | yes | 1.67 |
| Q06 | answered | Medium | 1/1 | yes | yes | 1.81 |
| Q07 | answered | Low | 3/3 | yes | yes | 1.04 |
| Q08 | answered | Medium | 1/1 | yes | yes | 1.1 |
| Q09 | answered | High | 2/2 | yes | yes | 1.06 |
| Q10 | answered | Medium | 1/1 | yes | yes | 0.92 |
| Q11 | model_declined | Medium | 0/2 | no | NO | 0.58 |
| N01 | no_evidence | None | 0/0 | no | yes | 0.01 |
| N02 | no_evidence | None | 0/0 | no | yes | 0.01 |
| N03 | no_evidence | None | 0/0 | no | yes | 0.01 |
| N04 | no_evidence | None | 0/0 | no | yes | 0.01 |
| N05 | model_declined | High | 0/0 | no | yes | 0.6 |
| N06 | no_evidence | None | 0/0 | no | yes | 0.01 |

### Answers

**Q01. Which software components are defined in the brake control system?**

The following software components (SW-Cs) are defined in the brake control system:

- **BrakeControlSWC** [Doc: vbcs_brake_system_hld.pdf, Page: 5, Section: 1.2 Scope]
- **WheelSpeedSensorSWC** [Doc: vbcs_brake_system_hld.pdf, Page: 5, Section: 1.2 Scope]
- **BrakePressureSensorSWC** [Doc: vbcs_brake_system_hld.pdf, Page: 5, Section: 1.2 Scope]
- **BrakeActuatorSWC** [Doc: vbcs_brake_system_hld.pdf, Page: 5, Section: 1.2 Scope]
- **VehicleStateManagerSWC** [Doc: vbcs_brake_system_hld.pdf, Page: 5, Section: 1.3 Definitions and Abbreviations]
- **DiagnosticManagerSWC** [Doc: vbcs_brake_system_hld.pdf, Page: 5, Section: 1.3 Definitions and Abbreviations]

**Q02. Which ports does BrakeControlSWC provide?**

The **provided ports** of **BrakeControlSWC** are:

- **PP_BrakeCommand** (Sender, interface **BrakeCommandIf**)
- **PP_ABSStatus** (Sender, interface **ABSStatusIf**)
- **PP_BrakeControlInfo** (Server, interface **BrakeControlInfoIf**)

[Doc: vbcs_brake_system_hld.pdf, Page: 8, Section: 3.2 BrakeControlSWC]

**Q03. Which signals are carried by WheelSpeedIf?**

The `WheelSpeedIf` interface carries the following signals:

- **WheelSpeed_FL** (float32, km/h)
- **WheelSpeed_FR** (float32, km/h)
- **WheelSpeed_RL** (float32, km/h)
- **WheelSpeed_RR** (float32, km/h)

[Doc: vbcs_brake_system_hld.pdf, Page: 15, Section: 6.3]

**Q04. What is the chain for functional flow FF-02?**

The chain for functional flow **FF-02** is:

**WheelSpeedSensorSWC → BrakeControlSWC → BrakeActuatorSWC**
[Doc: vbcs_brake_system_hld.pdf, Page: 18, Section: 8.2] (FF-02 description)
[Doc: vbcs_brake_system_hld.pdf, Page: 18, Section: 8.1] (Flow Overview Table 34)

**Q05. What does BrakeControlSWC do in degraded mode?**

In degraded mode, **BrakeControlSWC** performs the following actions:

- **Limits** `BrakeCommand` to **80%** of normal operation.
- **Calls** `SetActuatorPressureLimit` on `BrakeActuatorSWC` with a **pressure limit of 120 bar** (reduced from the default 200 bar).
- **Disables ABS** only if **wheel speed signals are invalid** (otherwise, ABS remains active).
- **Exits degraded mode** when `DegradedModeRequest` returns to **FALSE**, restoring the default pressure limit of **200 bar**.

[Doc: vbcs_brake_system_hld.pdf, Page: 24, Section: 12.1]
[Doc: vbcs_brake_system_hld.pdf, Page: 6, Section: 2.3]

**Q06. On which ECU is DiagnosticManagerSWC deployed?**

The **DiagnosticManagerSWC** is deployed on the **Brake Control Unit (BCU)**.

[Doc: vbcs_brake_system_hld.pdf, Page: 6, Section: 2.2 ECU Deployment]
[Doc: vbcs_brake_system_hld.pdf, Page: 11, Section: 3.7 DiagnosticManagerSWC]
[Doc: vbcs_brake_system_hld.pdf, Page: 11, Section: 3.7 DiagnosticManagerSWC]

**Q07. Which interfaces are Client-Server interfaces?**

The Client-Server interfaces are:

- **DiagnosticEventIf** [Doc: vbcs_brake_system_hld.pdf, Page: 13, Section: 5.1]
- **BrakeActuatorServiceIf** [Doc: vbcs_brake_system_hld.pdf, Page: 13, Section: 5.1]
- **BrakeControlInfoIf** [Doc: vbcs_brake_system_hld.pdf, Page: 13, Section: 5.1]

**Q08. Which CAN message broadcasts ABS_Active?**

The CAN message that broadcasts **ABS_Active** is:

- **ABS_STATUS_01 (CAN ID: 0x2B0)**
  [Doc: vbcs_brake_system_hld.pdf, Page: 15, Section: 6.2]
  [Doc: vbcs_brake_system_hld.pdf, Page: 16, Section: 7.2]

**Q09. When does DiagnosticManagerSWC run the actuator self-test?**

The **DiagnosticManagerSWC** runs the actuator self-test on **BrakeActuatorSWC** when:

- **VehicleMode equals `VEH_MODE_STANDBY`** [Doc: vbcs_brake_system_hld.pdf, Page: 23, Section: 10.4]
- Triggered via **RunActuatorSelfTest** on **BrakeActuatorServiceIf** [Doc: vbcs_brake_system_hld.pdf, Page: 11, Section: 3.7, Responsibility 5].

**Q10. Which port does ActuatorValves_SWC use to receive the valve command?**

ActuatorValves_SWC uses the port **R_ValveCmd** to receive the valve command.

[Doc: ebc_brake_ecu_hld.pdf, Page: 1, Section: 3]
[Doc: ebc_brake_ecu_hld.pdf, Page: 1, Section: 3]

**Q11. What data type and unit does BrakePressureCmd have in the EBC design?**

The provided AUTOSAR HLD documents do not contain sufficient evidence to answer this question.

**N01. What is the vehicle battery warranty replacement procedure?**

The provided AUTOSAR HLD documents do not contain sufficient evidence to answer this question.

**N02. What is the capital of France?**

The provided AUTOSAR HLD documents do not contain sufficient evidence to answer this question.

**N03. How do I bake sourdough bread?**

The provided AUTOSAR HLD documents do not contain sufficient evidence to answer this question.

**N04. How do I sort a list in Python?**

The provided AUTOSAR HLD documents do not contain sufficient evidence to answer this question.

**N05. Which ASIL is assigned to BrakeControlSWC?**

The provided AUTOSAR HLD documents do not contain sufficient evidence to answer this question.

**N06. What is the tyre pressure warning threshold?**

The provided AUTOSAR HLD documents do not contain sufficient evidence to answer this question.

