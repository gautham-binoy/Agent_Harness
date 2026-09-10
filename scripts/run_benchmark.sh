#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

if [ -f ".venv/bin/harness" ]; then
    HARNESS_BIN=".venv/bin/harness"
else
    HARNESS_BIN="harness"
fi

echo "=========================================================="
echo " Running Adaptive Coding Agent Harness Benchmark Suite    "
echo "=========================================================="

echo "Step 1: Running Baseline Benchmark..."
"$HARNESS_BIN" benchmark --config configs/baseline.yaml --dry-run

echo "Step 2: Running Full Adaptive Harness Benchmark..."
"$HARNESS_BIN" benchmark --config configs/developer.yaml --dry-run

echo "Step 3: Generating Comparison Report..."
"$HARNESS_BIN" compare --baseline baseline --candidate full-harness

echo "=========================================================="
echo " Benchmark suite and comparison report complete!          "
echo " Check reports/ directory for markdown and JSON summaries."
echo "=========================================================="
