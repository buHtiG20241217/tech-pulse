import pytest

from autosar_hld_assistant.app.core.vector_store import FAISSVectorStore, embedding_text


def _chunk(cid, doc, text, section=""):
    return {"chunk_id": cid, "document_name": doc, "page_number": 1, "section_header": section, "text": text}


CHUNKS = [
    _chunk("a1", "a.pdf", "WheelSpeedSensorSWC measures wheel velocity with four sensors."),
    _chunk("b1", "b.pdf", "BrakeControlSWC executes the ABS slip control algorithm."),
    _chunk("a2", "a.pdf", "The CAN network carries the brake pressure message every 10 ms."),
]


@pytest.fixture
def store(tmp_path):
    s = FAISSVectorStore(index_path=str(tmp_path / "i.bin"), metadata_path=str(tmp_path / "m.json"))
    s.add_chunks(CHUNKS)
    return s


def test_search_returns_nearest_first(store):
    results = store.search("wheel velocity sensors", top_k=3)
    assert results[0][0]["chunk_id"] == "a1"
    distances = [d for _, d in results]
    assert distances == sorted(distances) and distances[0] >= 0


def test_index_persists_and_reloads(store, tmp_path):
    reloaded = FAISSVectorStore(index_path=str(tmp_path / "i.bin"), metadata_path=str(tmp_path / "m.json"))
    assert reloaded.count() == 3
    assert reloaded.search("ABS slip control", top_k=1)[0][0]["chunk_id"] == "b1"


def test_remove_document_keeps_vectors_and_metadata_aligned(store):
    assert store.remove_document("a.pdf") == 2
    assert store.count() == 1 and store.chunk_counts() == {"b.pdf": 1}
    assert store.search("wheel velocity", top_k=1)[0][0]["chunk_id"] == "b1"
    assert store.remove_document("missing.pdf") == 0


def test_mismatched_files_are_reported(store, tmp_path):
    (tmp_path / "m.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        FAISSVectorStore(index_path=str(tmp_path / "i.bin"), metadata_path=str(tmp_path / "m.json"))


def test_section_heading_is_embedded_with_the_text():
    assert embedding_text(_chunk("x", "d", "body", "8.3 FF-02 Flow")) == "8.3 FF-02 Flow\nbody"
    assert embedding_text(_chunk("x", "d", "body")) == "body"
