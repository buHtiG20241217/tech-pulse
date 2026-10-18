# Declarations

| | |
|---|---|
| Student name | KIRAN SOORYA . R . S |
| Register number | 126003133 |
| University | SASTRA Deemed University |
| Programme | B.Tech Computer Science and Engineering |
| Project | AUTOSAR HLD Document Analysis Assistant (Case Study 1) |

---

## 1. Academic integrity declaration

I declare that:

- This submission is my original work, except where stated below.
- All external code, datasets, models and documents used are cited below.
- The results reported have not been fabricated; they can be reproduced with
  `Code/autosar_hld_assistant/evaluation/run_evaluation.py` and the test suite.
- This is an individual submission, and my contribution is stated accurately below.

### My contribution

- Selected Case Study 1 and defined the system: Streamlit UI, local embeddings, FAISS, Mistral LLM,
  SQLite storage, human-in-the-loop review.
- Built the first working version of the application (ingestion, entity extraction including the
  table parsers, grounded chat, review tab, export).
- Decided the fixes and features for the final version, tested the application, ran the evaluation.
- Recorded and narrated the demo video.

### External sources used

| Item | Type | Licence / source |
|---|---|---|
| Automotive Engineering AI Project Case Studies, Case Study 1 | Problem specification | Course material |
| Vehicle Brake Control System HLD (VBCHLD-001 rev 1.0, marked "Synthetic Test Document") | Main input / test document | Obtained from an external website |
| AUTOSAR EXP Virtual Functional Bus; CP SWS Platform Types; TR Foundation Release Overview | Reference documents | © AUTOSAR GbR, autosar.org |
| all-MiniLM-L6-v2 (sentence-transformers) | Pre-trained embedding model | Apache-2.0, HuggingFace |
| Mistral `ministral-8b-latest` | Pre-trained LLM via API | Mistral AI terms of service |
| Streamlit, FAISS, sentence-transformers, pypdf, OpenAI Python SDK, FastAPI, pandas, NumPy, python-dotenv, ReportLab, pytest | Libraries | Open-source (Apache-2.0 / MIT / BSD) |

Signature: R.S.KIRAN SOORYA   Date: 13-10-2026

---

## 2. AI-tool usage declaration

| AI model / tool | Purpose | Artifact affected | Verified by student |
|---|---|---|---|
| Claude Code (Anthropic, Claude Opus 5.5) | Coding and documentation assistant, working on my existing application | Refactoring and bug fixes in my original modules (`app/core`, `app/ingestion`, `app/extraction`, `app/rag`, `app/storage`, `app/reports`); UI redesign (`app/ui`); added modules `app/analysis`, `app/api.py`, `app/pipeline.py`; unit tests (`tests/`); evaluation script; sample revision 1.3; the files in `Documentation/` and `Model_Prompts_Config/`; the synopsis (`Synopsis/`); the technical report (`126003133_Report_v1.0.pdf`) and its screenshots (`Documentation/126003133_ReportFigures_v1.0/`); the narration script used for the demo video | Ran the full unit-test suite (84 tests, all passing); ran the evaluation script with and without the language model and checked the results against the documents; used every page of the application with the sample documents; checked answers against the cited PDF pages; read each module and can explain how it works |
| Mistral `ministral-8b-latest` | LLM inside the application: generates grounded answers; refines entity extraction | Runtime answers only (no code) | Evaluated with `run_evaluation.py --llm`; answers checked against cited pages |
| all-MiniLM-L6-v2 | Embedding model inside the application | Vector index (runtime) | Retrieval evaluated in `Evaluation_Results/` |

No other AI tools were used.

I remain accountable for the correctness of the submitted work and can explain all of it.

Signature: R.S.KIRAN SOORYA   Date: 13-10-2026
