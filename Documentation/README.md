# Documentation

AUTOSAR HLD Document Analysis Assistant: Case Study 1 of the Automotive Engineering AI case studies.

| Document | Contents |
|---|---|
| [126003133_Report_v1.0.pdf](../126003133_Report_v1.0.pdf) | **Technical report** (15 pages, in the submission's top folder; figures in `126003133_ReportFigures_v1.0/` here) |
| [126003133_Architecture_v1.0.md](126003133_Architecture_v1.0.md) | Problem, users, solution architecture, workflow diagrams, design decisions, case-study coverage |
| [126003133_UserGuide_v1.0.md](126003133_UserGuide_v1.0.md) | Installing, configuring and using the application; troubleshooting |
| [126003133_ModuleReference_v1.0.md](126003133_ModuleReference_v1.0.md) | Every source module: purpose, main classes and functions, behaviour |
| [126003133_DataModel_v1.0.md](126003133_DataModel_v1.0.md) | Input documents, stored files, database schema, internal data structures |
| [126003133_ResponsibleAI_v1.0.md](126003133_ResponsibleAI_v1.0.md) | Grounding, privacy, security and human-oversight measures |
| [126003133_Testing_v1.0.md](126003133_Testing_v1.0.md) | Test suite and how to run it |
| [126003133_KnownLimitations_v1.0.md](126003133_KnownLimitations_v1.0.md) | What the system does not do, and why |

Related folders in this submission:

| Folder | Contents |
|---|---|
| `../Code/autosar_hld_assistant` | Source code, tests, sample documents, evaluation script |
| `../Input_Data` | The HLD documents used as the knowledge base |
| `../Model_Prompts_Config` | Every LLM prompt and all model and retrieval settings |
| `../Evaluation_Results` | Evaluation report, raw results, unit-test log |

## Quick start

```powershell
cd ..\Code\autosar_hld_assistant
python -m pip install -r requirements.txt
$env:MISTRAL_API_KEY = "<your key>"     # optional; without it the app answers with passages only
.\launch.ps1                              # opens http://localhost:8501
```
