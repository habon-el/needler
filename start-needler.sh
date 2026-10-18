#!/bin/sh
# Start Needler on macOS/Linux: creates its Python environment on first run.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Setting up Needler for the first time..."
  python3 -m venv .venv && .venv/bin/python -m pip install --upgrade pip && .venv/bin/python -m pip install -e . || exit 1
fi
PYTHONPATH=src exec .venv/bin/python -X utf8 -m embroiderly.web
