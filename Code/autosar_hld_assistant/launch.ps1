# Starts the AUTOSAR HLD Assistant on http://localhost:8501
#
# The LLM key is never stored in this script. Provide it in one of these ways:
#   - a .env file in this folder (copy .env.example), or
#   - $env:MISTRAL_API_KEY = "<key>" in the shell before running, or
#   - the Model settings panel in the app's sidebar.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

python -c "import streamlit, faiss, sentence_transformers, pypdf, openai, dotenv" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing requirements..."
    python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "pip install failed. Run: python -m pip install -r requirements.txt" }
}

if (-not $env:MISTRAL_API_KEY -and -not (Test-Path .env)) {
    Write-Host "No MISTRAL_API_KEY found. Answers will be retrieval-only until a key is set in the sidebar." -ForegroundColor Yellow
}

python -m streamlit run app/main.py --server.port 8501
