# Module Reference

Source root: `Code/autosar_hld_assistant/`. Imports are rooted at the folder that contains
`autosar_hld_assistant`, e.g. `from autosar_hld_assistant.app.pipeline import ingest_pdf`.

```
app/
├── main.py                  Streamlit entry point and page navigation
├── api.py                   FastAPI REST service
├── pipeline.py              ingest / remove / reset (no UI code)
├── core/
│   ├── config.py            settings from environment and .env
│   ├── llm.py               LLMClient for Mistral or Azure OpenAI
│   ├── embeddings.py        LocalEmbedder (sentence-transformers)
│   └── vector_store.py      FAISSVectorStore
├── ingestion/
│   ├── pdf_parser.py        PDFDocumentParser, heading detection
│   └── chunker.py           DocumentChunker
├── extraction/
│   └── autosar_extractor.py AUTOSAREntityExtractor
├── rag/
│   ├── retriever.py         CitationRetriever
│   └── qa_engine.py         GroundedQAEngine, Answer, Citation
├── analysis/
│   ├── consistency.py       completeness and consistency checks
│   └── compare.py           revision comparison
├── storage/
│   ├── db.py                DatabaseManager, ENTITY_TABLES
│   └── hitl_store.py        HITLReviewManager
├── reports/
│   └── exporter.py          Markdown / JSON / CSV export
└── ui/
    ├── state.py             cached services, per-session LLM settings, sample list
    ├── sidebar.py           model settings, knowledge-base reset
    └── views/               documents, ask, architecture, compare, review, export
```

---

## core/config.py

Loads `.env` from the project folder (variables already set in the shell win), then defines the
constants below. `llm_settings_from_env()` returns an `LLMSettings` dataclass read at call time.

| Constant | Default | Env var |
|---|---|---|
| `DATA_DIR` | `<project>/data` | `AUTOSAR_DATA_DIR` |
| `UPLOADS_DIR` | `DATA_DIR/uploads` | — |
| `DB_PATH`, `FAISS_INDEX_PATH`, `FAISS_METADATA_PATH` | files in `DATA_DIR` | — |
| `EMBEDDING_MODEL_NAME`, `EMBEDDING_DIM` | `all-MiniLM-L6-v2`, 384 | — |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | 800, 150 characters | — |
| `RETRIEVAL_TOP_K` | 5 | `RETRIEVAL_TOP_K` |
| `SIMILARITY_THRESHOLD` | 1.1 (squared L2) | `SIMILARITY_THRESHOLD` |
| `LLM_EXTRACTION_CHARS` | 12000 | `LLM_EXTRACTION_CHARS` |

`LLMSettings` fields: `provider`, `mistral_api_key`, `mistral_model`, `mistral_base_url`,
`azure_endpoint`, `azure_api_key`, `azure_deployment`, `azure_api_version`.

## core/llm.py

- `LLMClient(settings=None)`: builds an `OpenAI` client (Mistral base URL) or an `AzureOpenAI`
  client when the credentials are present; otherwise it is unconfigured.
- `is_configured()`, `describe()` → e.g. `"Mistral · ministral-8b-latest"`.
- `chat(system_prompt, user_prompt, history=None, temperature=0.0, max_tokens=1500) -> str`
  forwards user and assistant turns from `history`. Raises `LLMNotConfigured` when there are no
  credentials, and `LLMError` (wrapping the SDK error) on failure.
- `chat_json(...)` → `dict | None`: requests provider JSON mode (max 6,000 tokens) and parses with
  `parse_json_reply`, which tolerates ```` ``` ```` fences and keeps the complete items of a reply cut off by
  the token limit.

## core/embeddings.py

`LocalEmbedder.embed_text(text)` → `(384,)` and `embed_batch(texts)` → `(N, 384)`, float32,
L2-normalised. The model loads once per process (`functools.lru_cache`). If it cannot be loaded,
`EmbeddingModelUnavailable` is raised; the UI shows it as an error instead of continuing with
meaningless vectors.

## core/vector_store.py

`FAISSVectorStore(index_path, metadata_path, dim, embedder)`, backed by an exact `IndexFlatL2`.
`metadata[i]` describes vector `i`.

| Method | Behaviour |
|---|---|
| `add_chunks(chunks)` | Embeds `embedding_text(chunk)` = section heading + text; appends; saves |
| `search(query, top_k)` | `[(chunk, squared_L2_distance)]`, nearest first |
| `remove_document(name)` | `index.remove_ids` + matching metadata filter, which keeps them aligned; saves |
| `chunk_counts()`, `count()`, `clear()` | Per-document counts, total, reset |
| `save()` / `load()` | Writes via temporary files + `os.replace` (atomic); `load` raises if index and metadata sizes differ |

Squared L2 between unit vectors is `2 − 2·cos θ`: 0 means identical, 2 means unrelated.

## ingestion/pdf_parser.py

`PDFDocumentParser(path).parse()` → `{document_name, file_path, total_pages, pages[], full_text}`.
Each page carries `text`, `headings` as `[(offset, "3.3 WheelSpeedSensorSWC")]`,
`section_at_start` and `is_contents`.

`find_headings(text)` accepts `1. Title`, `3.2 Title` and `Section 4. Title`. To exclude numbered
sentences, the title must be at most 10 words and must not end in `. , ; :`. A page with 12 or more
headings is treated as a table of contents: its headings are ignored and it is not chunked.

## ingestion/chunker.py

`DocumentChunker(chunk_size=800, chunk_overlap=150).create_chunks(parsed)` slides a window over
each page separately, so a chunk never spans two pages. Each chunk is labelled with the section in
force at its midpoint (`section_at`). Chunk fields: `chunk_id` (`<doc>_p<page>_c<n>`),
`document_name`, `page_number`, `section_header`, `text`.

## extraction/autosar_extractor.py

`AUTOSAREntityExtractor().extract_all(text, document_name, llm=None)` returns
`{document_name, swcs, interfaces, ports, signals, dependencies, functional_flows}`.

1. **Name regexes**: `…SWC`, `…_If`/`…If`, `PP_/RP_/P_/R_…`, signal-like suffixes,
   `A_SWC -> B_SWC (via X_If)`, `Flow: A -> B`. `Flow:` lines are excluded from dependencies.
2. **Table rows** (authoritative; each one found replaces the regex result for its type):
   - ID-numbered rows: `SWC-nn`, `IF-nn`, `P-nn`, `D-nn`, signal mapping and definition rows, and
     `n.n FF-nn` headings with `Chain:` lines.
   - Plain rows without IDs: `Name_SWC Application …`, `P_X Provided Owner_SWC X_If`,
     `Sig float32 km/h X_If`.
3. **LLM pass** (on by default in the UI when a model is configured): `select_llm_input` picks the pages
   with the most architecture names, in page order, up to `LLM_EXTRACTION_CHARS`, and sends them with a
   JSON schema prompt. `merge_entities(..., fill_only=True)` fills only missing or placeholder fields.
   New elements are added (as `source = "llm"`) only for kinds the document has no table for
   (`add_new=False` otherwise), so a table stays the complete list.
4. **Filters**: 38 AUTOSAR Basic Software module names (`BSW_MODULES`) are never SW-Cs or
   interfaces. Signals named like ports (`PP_`, `RP_`, `EVT_`) or operations (`Get…`, `Set…`) are
   dropped.

Merge keys (`MERGE_KEYS`): ports by *(owner, name)*, because one port name can exist on several
SW-Cs; dependencies by *(source, interface, target)*.

## rag/retriever.py

`CitationRetriever.retrieve(query, top_k)` delegates to the vector store.
`format_context(hits)` builds the numbered `[i] Doc: …, Page: …, Section: …` passages for the prompt.

## rag/qa_engine.py

`GroundedQAEngine(retriever=None, vector_store=None, threshold=1.1, top_k=5)`.

- `find_evidence(question, history)`: retrieve; if the best distance exceeds the threshold and
  the question refers back to an earlier one (`is_follow_up`: words such as *it, its, those* and no
  element name), retry with the previous user question combined.
- `answer_question(question, history=None, llm=None)` → `Answer(question, text, status, citations)`.

| `AnswerStatus` | Meaning |
|---|---|
| `answered` | LLM answered from the passages |
| `no_evidence` | Nothing close enough; LLM not called |
| `model_declined` | LLM replied with the fixed refusal sentence |
| `no_llm` | Passages found, no model configured |
| `llm_error` | Provider call failed (message shown) |

`Answer.grounded` is true only for `answered`. `Answer.confidence` is `High` (best distance ≤ 0.75),
`Medium` (≤ 0.95), `Low` (above that) or `None` (no passages). Only the last 6 conversation turns
are sent to the model. Prompts: `../Model_Prompts_Config/126003133_Prompts_v1.0.md`.

## analysis/consistency.py

`check_architecture(data)` / `check_document(db, name)` → `[Finding(severity, check, element,
message)]`, sorted Error → Warning → Info. The rules are in 126003133_Architecture_v1.0.md §3.4. Checks that need
port owners are skipped when the document gave none.

## analysis/compare.py

`compare_documents(db, old, new)` → `{kind: KindDiff(added, removed, changed[Change(element,
field, old, new)])}`, matched by `IDENTITY` keys.

## storage/db.py

`ENTITY_TABLES` maps each kind to an `EntityTable` (table name, label, columns, defaults,
editable columns, reviewable). The schema is generated from this map; see 126003133_DataModel_v1.0.md.

| Method | Purpose |
|---|---|
| `connect()` | Context manager: commit on success, rollback on error, always close |
| `add_document`, `has_document`, `list_documents`, `delete_document` | Document registry; delete keeps reviews |
| `save_extracted_entities(extracted)` | Inserts all kinds with defaults and `source` |
| `get_entities(kind, document=None)`, `get_entity(kind, id)`, `count_entities(document=None)` | Reads |
| `update_entity(kind, id, changes)` | Only editable columns and `review_status`; anything else raises `ValueError` |
| `clear_all(include_reviews=False)` | Reset; keeps the review log unless asked |

`_migrate` adds columns introduced after the first version (`source`, `entity_id`,
`document_name` on reviews) to existing databases.

## storage/hitl_store.py

`HITLReviewManager.log_review(kind, entity_id, status, reviewer, rationale, risk_notes="",
corrections=None)` validates the input (`ReviewError` on an unknown status, an empty reviewer or
rationale, or *Edited* without changes). In one transaction it appends to `hitl_reviews` (with
`{"field": {"old", "new"}}` for edits) and updates the element and its `review_status`.
`get_all_reviews()` returns the log newest first. `entity_label` writes ports as `Owner.Port`.

## reports/exporter.py

`ArchitectureReportExporter(db, hitl)`:
- `generate_markdown_report()`: summary with review counts, then SW-Cs, interfaces, ports,
  signals, dependencies, flows, consistency findings and the review log.
- `generate_json_export()`, `generate_csv_exports()`, `generate_csv_zip()`.

## pipeline.py

- `ingest_pdf(path, store, db, extractor=None, llm=None, progress=callback) -> IngestResult`.
  Re-ingesting replaces the document; an image-only PDF raises `ValueError`.
- `remove_document`, `reset_knowledge_base`.
- `save_upload(name, bytes)` writes to `data/uploads/` under `safe_filename(name)`, which drops
  directories and unsafe characters.

## api.py

| Method and path | Purpose |
|---|---|
| `GET /documents` | Indexed documents with passage counts |
| `POST /documents` (multipart `file`) | Index a PDF (415 if not a PDF, 422 if no text) |
| `DELETE /documents/{name}` | Remove a document |
| `GET /entities/{kind}?document=` | Extracted elements |
| `POST /ask` `{question, history}` | Answer with status, confidence and citations (uses the env LLM settings) |
| `GET /checks/{name}` | Consistency findings |
| `GET /compare?old=&new=` | Revision comparison |
| `POST /reviews`, `GET /reviews` | Record a review decision, read the log |

## ui/

`state.services()` is cached per server process (`st.cache_resource`) and holds the store,
database, review manager, QA engine, exporter and a write lock. LLM settings live in
`st.session_state`, so they are per browser session. Each module in `views/` exposes `render()`;
`main.py` registers them with `st.navigation(position="top")`. The theme (light and dark) is in
`.streamlit/config.toml`.
