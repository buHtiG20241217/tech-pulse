"""FAISS index of document chunks, persisted next to a JSON metadata file."""

from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any

import faiss
import numpy as np

from autosar_hld_assistant.app.core.config import EMBEDDING_DIM, FAISS_INDEX_PATH, FAISS_METADATA_PATH
from autosar_hld_assistant.app.core.embeddings import LocalEmbedder


def embedding_text(chunk: dict[str, Any]) -> str:
    """Text that is embedded for a chunk: its section heading plus its body.

    The heading carries the topic ("8.3 FF-02 Wheel-Speed to Brake-Command
    Flow") that table-heavy bodies often lack.
    """
    section = chunk.get("section_header") or ""
    return f"{section}\n{chunk['text']}" if section else chunk["text"]


class FAISSVectorStore:
    """Exact L2 search over chunk embeddings.

    `metadata[i]` describes vector `i`. Both are written to disk after every
    change.
    """

    def __init__(
        self,
        index_path: str = FAISS_INDEX_PATH,
        metadata_path: str = FAISS_METADATA_PATH,
        dim: int = EMBEDDING_DIM,
        embedder: LocalEmbedder | None = None,
    ):
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.dim = dim
        self.embedder = embedder or LocalEmbedder()
        self.metadata: list[dict[str, Any]] = []
        self.index = faiss.IndexFlatL2(dim)

        if os.path.exists(index_path) and os.path.exists(metadata_path):
            self.load()

    def add_chunks(self, chunks: list[dict[str, Any]]) -> int:
        if not chunks:
            return 0
        vectors = self.embedder.embed_batch([embedding_text(c) for c in chunks])
        self.index.add(vectors)
        self.metadata.extend(chunks)
        self.save()
        return len(chunks)

    def search(self, query: str, top_k: int = 5) -> list[tuple[dict[str, Any], float]]:
        """Return up to `top_k` (chunk, squared L2 distance) pairs, nearest first."""
        if self.index.ntotal == 0:
            return []
        query_vec = self.embedder.embed_text(query).reshape(1, -1)
        distances, indices = self.index.search(query_vec, min(top_k, self.index.ntotal))
        return [
            (self.metadata[idx], float(dist))
            for idx, dist in zip(indices[0], distances[0])
            if 0 <= idx < len(self.metadata)
        ]

    def remove_document(self, document_name: str) -> int:
        """Drop every chunk of one document. Returns the number removed."""
        doomed = [i for i, m in enumerate(self.metadata) if m.get("document_name") == document_name]
        if not doomed:
            return 0
        # IndexFlat.remove_ids compacts the index and keeps the remaining order,
        # so filtering the metadata list the same way keeps them aligned.
        self.index.remove_ids(np.array(doomed, dtype="int64"))
        doomed_set = set(doomed)
        self.metadata = [m for i, m in enumerate(self.metadata) if i not in doomed_set]
        self.save()
        return len(doomed)

    def chunk_counts(self) -> dict[str, int]:
        """Number of chunks per document name."""
        return dict(Counter(m.get("document_name", "") for m in self.metadata))

    def count(self) -> int:
        return self.index.ntotal

    def clear(self) -> None:
        self.index = faiss.IndexFlatL2(self.dim)
        self.metadata = []
        self.save()

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.index_path) or ".", exist_ok=True)
        tmp_index = self.index_path + ".tmp"
        tmp_meta = self.metadata_path + ".tmp"
        faiss.write_index(self.index, tmp_index)
        with open(tmp_meta, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False)
        os.replace(tmp_index, self.index_path)
        os.replace(tmp_meta, self.metadata_path)

    def load(self) -> None:
        self.index = faiss.read_index(self.index_path)
        with open(self.metadata_path, encoding="utf-8") as f:
            self.metadata = json.load(f)
        if self.index.ntotal != len(self.metadata):
            raise ValueError(
                f"Vector index has {self.index.ntotal} vectors but metadata has "
                f"{len(self.metadata)} entries; delete {self.index_path} and re-index."
            )
