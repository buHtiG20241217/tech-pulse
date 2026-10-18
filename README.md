# AUTOSAR HLD Document Analysis Assistant

Capstone project: Case Study 1, *AUTOSAR HLD Document Analysis Assistant*.
SASTRA Deemed University · Register number 126003133.

An assistant that indexes AUTOSAR High-Level Design PDFs and then:
- extracts the architecture (SW-Cs, interfaces, ports, signals, dependencies, functional flows);
- answers questions with page and section citations, refusing when the documents hold no evidence;
- checks the design for inconsistencies and compares revisions;
- keeps an engineer in the loop to approve or correct every extracted element.

| Folder | Contents |
|---|---|
| `Synopsis/` | Project synopsis |
| `Input_Data/` | HLD documents and AUTOSAR reference documents used as the knowledge base |
| `Code/autosar_hld_assistant/` | Application source, tests, sample documents, evaluation script |
| `Model_Prompts_Config/` | All LLM prompts, model and retrieval configuration |
| `Evaluation_Results/` | Evaluation report and raw results, unit-test log |
| `Documentation/` | Technical report, architecture, user guide, module reference, Responsible AI |
| `Video/` | Demonstration video |
| `Declarations/` | Academic integrity and AI-tool usage declarations |

## Run

```powershell
cd Code\autosar_hld_assistant
python -m pip install -r requirements.txt
$env:MISTRAL_API_KEY = "<your key>"     # optional: without it, answers show retrieved passages only
.\launch.ps1                              # http://localhost:8501
```

Tests: `python -m pytest` (84 tests). Evaluation: `python evaluation\run_evaluation.py`.
