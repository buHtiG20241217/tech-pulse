"""Runtime configuration.

Values come from environment variables. A `.env` file in the project root is
loaded first if present; variables already set in the environment win.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

# Storage
DATA_DIR = Path(os.getenv("AUTOSAR_DATA_DIR", str(BASE_DIR / "data")))
UPLOADS_DIR = DATA_DIR / "uploads"
SAMPLES_DIR = BASE_DIR / "samples"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = str(DATA_DIR / "autosar_hld.db")
FAISS_INDEX_PATH = str(DATA_DIR / "faiss_index.bin")
FAISS_METADATA_PATH = str(DATA_DIR / "faiss_metadata.json")

# Embeddings (run locally on CPU)
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Chunking
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

# Retrieval and grounding
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))
# Squared L2 distance between unit vectors (0 = identical, 2 = unrelated).
# If the best passage is further away than this, the question is not sent to
# the LLM. See docs/evaluation.md for how the value was chosen.
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "1.1"))

# LLM entity extraction: character budget for the pages sent to the model.
LLM_EXTRACTION_CHARS = int(os.getenv("LLM_EXTRACTION_CHARS", "12000"))


@dataclass(frozen=True)
class LLMSettings:
    provider: str = "mistral"
    mistral_api_key: str = ""
    mistral_model: str = "ministral-8b-latest"
    mistral_base_url: str = "https://api.mistral.ai/v1"
    azure_endpoint: str = ""
    azure_api_key: str = ""
    azure_deployment: str = "gpt-4o-mini"
    azure_api_version: str = "2024-08-01-preview"


def llm_settings_from_env() -> LLMSettings:
    """Read LLM settings from the environment at call time."""
    defaults = LLMSettings()
    return LLMSettings(
        provider=os.getenv("LLM_PROVIDER", defaults.provider).strip().lower(),
        mistral_api_key=os.getenv("MISTRAL_API_KEY", ""),
        mistral_model=os.getenv("MISTRAL_MODEL", defaults.mistral_model),
        mistral_base_url=os.getenv("MISTRAL_BASE_URL", defaults.mistral_base_url),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        azure_api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", defaults.azure_deployment),
        azure_api_version=os.getenv("AZURE_OPENAI_API_VERSION", defaults.azure_api_version),
    )
