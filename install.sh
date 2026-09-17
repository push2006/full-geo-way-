#!/usr/bin/env bash
# Quick setup: python venv + deps + .env, no manual steps.
#   curl -fsSL <raw-url-to-this-file> | bash
#   or, locally: ./install.sh
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
    echo "python3 not found. Install Python 3.10+ first." >&2
    exit 1
}

echo "→ Creating virtual environment (.venv)..."
"$PYTHON_BIN" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "→ Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ ! -f .env ]; then
    echo "→ Creating .env from .env.example..."
    cp .env.example .env
else
    echo "→ .env already exists, leaving it alone."
fi

echo
echo "Done. To start:"
echo "  source .venv/bin/activate"
echo "  python run.py"
echo
echo "Then open http://127.0.0.1:8501"
