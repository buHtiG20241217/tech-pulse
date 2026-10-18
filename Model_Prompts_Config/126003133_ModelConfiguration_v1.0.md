# Model and Pipeline Configuration

Configuration is read from environment variables, or from a `.env` file in
`Code/autosar_hld_assistant/` (template: `126003133_EnvTemplate_v1.0.env` in this folder). Values set in the shell
take precedence.

## Pre-trained models

| Model | Role | Where it runs | Fine-tuned |
|---|---|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` | Embeds passages and questions (384-d, normalised) | Locally on CPU; downloaded once from HuggingFace | No |
| `ministral-8b-latest` (default) | Answers questions; refines entity extraction | Mistral AI API (OpenAI-compatible) | No |
| `gpt-4o-mini` deployment (alternative) | Same role | The user's Azure OpenAI resource | No |

## Language model settings

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `mistral` | `mistral` or `azure` |
| `MISTRAL_API_KEY` | (empty) | Without a key the app runs in retrieval-only mode |
| `MISTRAL_MODEL` | `ministral-8b-latest` | Other choices in the sidebar: mistral-small, medium, large (paid), open-mistral-nemo, or any model ID |
| `MISTRAL_BASE_URL` | `https://api.mistral.ai/v1` | |
| `AZURE_OPENAI_ENDPOINT` | (empty) | `https://<resource>.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | (empty) | |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o-mini` | |
| `AZURE_OPENAI_API_VERSION` | `2024-08-01-preview` | |

Generation: temperature 0.0; max tokens 1,500 (answers) or 6,000 (extraction, JSON mode); last 6 chat turns.

## Retrieval and grounding settings

| Setting | Value | Variable / location |
|---|---|---|
| Chunk size / overlap | 800 / 150 characters, per page | `CHUNK_SIZE`, `CHUNK_OVERLAP` in `app/core/config.py` |
| Text embedded per chunk | section heading + chunk text | `embedding_text()` in `app/core/vector_store.py` |
| Contents pages | not indexed (page with ≥ 12 headings) | `app/ingestion/pdf_parser.py` |
| Index | FAISS `IndexFlatL2` (exact) | `app/core/vector_store.py` |
| Passages retrieved | 5 | `RETRIEVAL_TOP_K` |
| Grounding threshold | 1.1 squared L2 (≈ cosine ≥ 0.45) | `SIMILARITY_THRESHOLD` |
| Confidence bands | High ≤ 0.75, Medium ≤ 0.95, Low above | `app/rag/qa_engine.py` |
| LLM extraction window | 12,000 characters from the most architecture-dense pages | `LLM_EXTRACTION_CHARS` |

How the threshold and bands were chosen: `../Evaluation_Results/126003133_EvaluationReport_v1.0.md`, sections
*Retrieval and grounding gate* and *threshold sweep*.

## Application settings

| Setting | Value | Location |
|---|---|---|
| Data folder | `Code/autosar_hld_assistant/data` | `AUTOSAR_DATA_DIR` |
| Upload limit | 50 MB | `.streamlit/config.toml` (copy: `126003133_StreamlitConfig_v1.0.toml`) |
| Usage statistics | off | `.streamlit/config.toml` |
| Theme | light and dark, blue accent | `.streamlit/config.toml` |
