#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "=== Running Adaptive Agent Harness Demo ==="

if [ -f ".venv/bin/harness" ]; then
    HARNESS_BIN=".venv/bin/harness"
else
    HARNESS_BIN="harness"
fi

"$HARNESS_BIN" demo --dry-run
