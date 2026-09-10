#!/usr/bin/env bash
set -e

echo "=== Setting up Adaptive Coding Agent Harness ==="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3.11+ is required but not installed."
    exit 1
fi

echo "Creating Python virtual environment (.venv)..."
python3 -m venv .venv

echo "Installing harness dependencies..."
.venv/bin/pip install --upgrade pip wheel
.venv/bin/pip install -e .
.venv/bin/pip install pytest httpx

echo "Verifying OpenCode CLI..."
if command -v opencode &> /dev/null; then
    echo "Found OpenCode: $(which opencode)"
    opencode --version 2>&1 || true
else
    echo "Notice: 'opencode' command not detected in PATH. Mock/dry-run mode is fully enabled."
fi

if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

echo "=== Setup Completed Successfully! ==="
echo "You can now run:"
echo "  source .venv/bin/activate"
echo "  harness --help"
echo "  ./scripts/run_demo.sh"
