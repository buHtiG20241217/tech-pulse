# Known Limitations

| Area | Limitation | Possible next step |
|---|---|---|
| Scanned PDFs | No OCR; image-only PDFs are rejected with a message | Add Tesseract (pytesseract) for pages without a text layer |
| Table layouts | Table parsers expect ID-numbered rows (`SWC-01`, `P-01`, …) or plain `name / type / …` rows. Other layouts fall back to name heuristics | Add layouts as needed, or use a table-aware parser (pdfplumber) |
| Diagrams | Architecture shown only in figures is not read | Out of scope for a text pipeline |
| Threshold calibration | 1.1 was chosen on 17 questions over the sample documents; the margin between the hardest answerable (1.05) and the nearest off-topic question (1.16) is small | Re-calibrate with `evaluation/run_evaluation.py` on real project documents |
| On-topic but unanswerable questions | Pass the distance gate (e.g. an ASIL question, 0.51); refusal then depends on the model following the prompt | A second-stage check (answer-to-passage entailment) |
| LLM extraction window | The model sees up to 12,000 characters, chosen from the pages with the most architecture names; elements elsewhere rely on the rule-based parsers | Run the LLM pass page by page |
| Small model | ministral-8b sometimes declines a question its passages do answer (1 of 11 in the evaluation, Q11) | Larger model, or more passages per question |
| Answer correctness | `grounded` means "answered from passages", not "verified correct" | Human review; citation spot checks |
| Access control | No login, roles or project isolation; REST API unauthenticated | Add authentication in front of the API (case study "Scale" phase) |
| Concurrency | One local user; writes are serialised with a lock | PostgreSQL and a vector server for multi-user use |
| Scale | Exact FAISS search; fine up to tens of thousands of chunks | IVF/HNSW index |
| Deployment | Local Python application, no Docker image | Add a Dockerfile |
| UI tests | Streamlit pages have no automated tests | `streamlit.testing.v1.AppTest` |
