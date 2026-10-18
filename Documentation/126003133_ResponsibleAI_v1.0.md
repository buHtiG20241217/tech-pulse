# Responsible AI Measures

## 1. Grounding

| Measure | Where | Effect |
|---|---|---|
| Retrieval-Augmented Generation | `rag/qa_engine.py` | The model sees only passages from the indexed documents |
| Evidence gate before generation | `SIMILARITY_THRESHOLD = 1.1` | If no passage is close enough, the question is refused and **the LLM is never called** |
| Strict prompt | `SYSTEM_PROMPT` | Use only the passages; no general knowledge; cite each statement; fixed refusal sentence |
| Refusal detection | `AnswerStatus.MODEL_DECLINED` | The fixed refusal sentence is detected in code and shown as "not answered" |
| Deterministic decoding | `temperature = 0.0` | Repeatable, factual answers |
| Citations and evidence | Ask → *Sources* | Document, page, section, distance and the raw passage for every answer |
| Confidence indicator | `Answer.confidence` | High / Medium / Low evidence match, shown with every answer |
| Deterministic extraction | `autosar_extractor.py` | Inventory comes from table parsing; the LLM may fill gaps but cannot add to a kind the document defines in a table; its additions are labelled `llm`, and domain filters (BSW modules, port names) apply to its output too |

Measured on the evaluation set (`../Evaluation_Results/`):
- 11/11 answerable questions passed the gate.
- 5/6 unanswerable questions were blocked before reaching the model.
- With the model (ministral-8b-latest): 10/11 answerable questions answered correctly, all with inline citations; 6/6 unanswerable questions refused (5 by the evidence check, the ASIL question by the model itself).
- The sixth, *"Which ASIL is assigned to BrakeControlSWC?"*, is on topic but not covered by the
  documents. It relies on the prompt rule and the refusal check.

## 2. Privacy

| Data | Leaves the machine? |
|---|---|
| PDFs, embeddings, vector index, extracted elements, review log | No. Embeddings are computed locally on the CPU |
| A question, its top 5 passages (≤ ~4,000 characters) and the last 6 chat turns | Yes, to the configured LLM provider |
| Up to 12,000 characters taken from the document's most architecture-dense pages | When indexing with *Refine extraction with the language model* on (the default when a model is configured; it can be switched off) |
| Usage statistics | No (`gatherUsageStats = false`) |

For confidential documents, use Azure OpenAI in the organisation's own tenant, or run without a model:
extraction, search, citations, checks, comparison and review all work offline. The only personal data
stored is the reviewer name typed into the review form.

## 3. Security

- API keys come from the environment or `.env` (git-ignored) or are typed into the sidebar. They are
  never written to code or to disk by the app. Sidebar settings are per browser session.
- Key fields are masked in the UI.
- All SQL uses parameter placeholders. Table names come from a fixed internal map, never from input.
- Uploads: PDF only; names sanitised (`safe_filename`) to prevent path traversal; 50 MB limit
  (`.streamlit/config.toml`).
- Index files are written atomically and checked for consistency on load.
- Prompt injection: the model has no tools and cannot act. Injected text in a document can at most
  distort an answer, and the cited passage lets the reader see it.
- Limits: no login or role-based access (local pilot). The REST API has no authentication and is for
  local use only.

## 4. Human oversight

- Every extracted element starts as **Pending**.
- An engineer records **Approved**, **Rejected** or **Edited**. A reviewer name and a rationale are
  mandatory; safety and risk notes are optional.
- Edits apply the corrected values and log the old and new value of every changed field.
- The review log is append-only, timestamped, shown in the app, included in every export, and kept
  when documents are removed or the knowledge base is reset (unless explicitly deleted).
- Consistency findings are suggestions for review; nothing is changed automatically.
- The system never approves anything itself, in line with the case study's governance principle that
  AI output is reviewed by authorised engineers before use.
