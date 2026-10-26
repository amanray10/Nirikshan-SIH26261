#!/usr/bin/env bash
# One-time setup on Linux/macOS.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv backend/.venv
backend/.venv/bin/pip install --upgrade pip
backend/.venv/bin/pip install -r backend/requirements.txt
(cd frontend && npm install && npm run build)
command -v tesseract >/dev/null || echo "Install Tesseract (apt install tesseract-ocr tesseract-ocr-hin tesseract-ocr-mar / brew install tesseract) to read scans."
(cd backend && .venv/bin/python scripts/seed.py --regenerate && .venv/bin/python scripts/evaluate.py && .venv/bin/python -m pytest -q)
echo "Done. Start with: scripts/run.sh"
