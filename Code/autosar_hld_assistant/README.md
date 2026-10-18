# AUTOSAR HLD Assistant: source code

Streamlit application and REST API for extracting, querying, checking and reviewing AUTOSAR
High-Level Design documents. Full documentation is in `../../Documentation/`.

## Setup

Python 3.10+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env     # then set MISTRAL_API_KEY (optional)
```

## Run

```powershell
.\launch.ps1                    # or: python -m streamlit run app/main.py
```

REST API (from the parent folder): `python -m uvicorn autosar_hld_assistant.app.api:app --port 8000`,
with interactive docs at `/docs`.

## Test and evaluate

```powershell
python -m pytest                          # 84 tests, no network needed
python evaluation\run_evaluation.py       # add --llm to include model answers
```

## Layout

| Path | Contents |
|---|---|
| `app/main.py` | Streamlit entry point |
| `app/ui/` | Pages (`views/`), sidebar, shared state |
| `app/pipeline.py` | Ingest, remove, reset |
| `app/core/` | Configuration, LLM client, embeddings, FAISS store |
| `app/ingestion/` | PDF parsing, chunking |
| `app/extraction/` | AUTOSAR element extraction |
| `app/rag/` | Retrieval and grounded question answering |
| `app/analysis/` | Consistency checks, revision comparison |
| `app/storage/` | SQLite storage, review log |
| `app/reports/` | Markdown / JSON / CSV export |
| `app/api.py` | FastAPI service |
| `samples/` | Sample HLDs and the generator for the EBC samples |
| `evaluation/` | Evaluation script, questions, ground truth |
| `tests/` | Unit tests |
| `.streamlit/config.toml` | Theme and server settings |
| `data/` | Created at run time: index, database, uploads (safe to delete) |
