#!/usr/bin/env bash
# DSS Setup Script
# Run this once to install all dependencies before launching the DSS Electron app.

set -e

echo ""
echo "=== DSS (Distributed Storage System) — Setup ==="
echo ""

if ! command -v python3 &>/dev/null; then
  echo "ERROR: Python 3 is not installed."
  echo "Download it from https://www.python.org/downloads/ and re-run this script."
  exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python version: $PY_VER"

if ! command -v node &>/dev/null; then
  echo "ERROR: Node.js is not installed."
  echo "Download it from https://nodejs.org/ and re-run this script."
  exit 1
fi

echo "  Node.js version: $(node --version)"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Installing Python dependencies..."
python3 -m pip install --upgrade pip --quiet
python3 -m pip install -r requirements.txt --quiet
echo "  Python dependencies installed."
echo ""

echo "Installing UI dependencies..."
cd ui
npm install --silent
echo "  UI dependencies installed."
cd "$SCRIPT_DIR"

echo "Installing Electron dependencies..."
cd electron
npm install --silent
echo "  Electron dependencies installed."
cd "$SCRIPT_DIR"

echo ""
echo "=== Setup complete! ==="
echo ""
echo "To launch DSS:"
echo "  1. Start the UI:      cd ui && npm run dev"
echo "  2. Launch Electron:   cd electron && npm start"
echo ""
echo "Or run the full test suite:"
echo "  cd $SCRIPT_DIR && python3 -m pytest tests/ -v"
echo ""
