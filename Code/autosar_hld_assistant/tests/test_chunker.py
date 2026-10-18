import pytest

from autosar_hld_assistant.app.ingestion.chunker import DocumentChunker, section_at


def _doc(*pages):
    return {"document_name": "d.pdf", "pages": list(pages)}


def _page(number, text, headings=(), start="Front matter"):
    return {"page_number": number, "text": text, "headings": list(headings), "section_at_start": start}


def test_section_at_uses_last_heading_before_offset():
    page = _page(1, "x" * 100, headings=[(10, "1 A"), (50, "2 B")], start="0 Intro")
    assert section_at(0, page) == "0 Intro"
    assert section_at(10, page) == "1 A"
    assert section_at(99, page) == "2 B"


def test_chunks_never_span_pages_and_keep_citation_fields():
    doc = _doc(_page(1, "a" * 1000), _page(2, "b" * 300))
    chunks = DocumentChunker(chunk_size=400, chunk_overlap=100).create_chunks(doc)
    assert [c["page_number"] for c in chunks] == [1, 1, 1, 2]
    assert all(set(c["text"]) == {"a"} for c in chunks[:3])
    assert chunks[0]["chunk_id"] == "d.pdf_p1_c1"
    assert {"document_name", "section_header", "text"} <= chunks[0].keys()


def test_overlap_is_applied():
    text = "".join(str(i % 10) for i in range(700))
    first, second = DocumentChunker(chunk_size=400, chunk_overlap=100).create_chunks(_doc(_page(1, text)))[:2]
    assert first["text"][-100:] == second["text"][:100]


def test_blank_pages_produce_no_chunks():
    assert DocumentChunker().create_chunks(_doc(_page(1, "   "))) == []


def test_invalid_overlap_is_rejected():
    with pytest.raises(ValueError):
        DocumentChunker(chunk_size=100, chunk_overlap=100)
