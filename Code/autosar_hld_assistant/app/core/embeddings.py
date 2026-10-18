"""Local sentence embeddings (SentenceTransformers, CPU)."""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from autosar_hld_assistant.app.core.config import EMBEDDING_DIM, EMBEDDING_MODEL_NAME


class EmbeddingModelUnavailable(RuntimeError):
    """The embedding model could not be loaded (usually: no network on first run)."""


@lru_cache(maxsize=None)
def _load_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    try:
        return SentenceTransformer(model_name)
    except Exception as exc:
        raise EmbeddingModelUnavailable(
            f"Could not load embedding model '{model_name}': {exc}. "
            "It is downloaded from HuggingFace on first use; check the network or set HF_TOKEN."
        ) from exc


class LocalEmbedder:
    """Turns text into L2-normalised float32 vectors.

    The model is loaded once per process and shared by all instances.
    """

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        self.dim = EMBEDDING_DIM

    def embed_text(self, text: str) -> np.ndarray:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dim), dtype=np.float32)
        model = _load_model(self.model_name)
        vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return vectors.astype(np.float32)
