"""Test setup shared by everything under tests/.

- Makes `autosar_hld_assistant` importable when pytest runs from this folder.
- Points data storage at a throwaway directory.
- Blanks LLM credentials so no test can reach a real API, even if a .env
  file exists (python-dotenv does not override variables that are set).
"""

import os
import sys
import tempfile
from pathlib import Path

_PROJECT = Path(__file__).resolve().parent
for path in (_PROJECT.parent, _PROJECT):  # package root, and the folder holding tests/
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ["AUTOSAR_DATA_DIR"] = tempfile.mkdtemp(prefix="autosar_test_data_")
for var in ("MISTRAL_API_KEY", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"):
    os.environ[var] = ""
os.environ["LLM_PROVIDER"] = "mistral"
