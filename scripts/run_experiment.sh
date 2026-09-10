#!/usr/bin/env bash
# ==============================================================================
# Adaptive Coding Agent Harness — Reproducible Experiment Runner
# Compares Baseline vs Ablations vs Full Harness with repeated runs & metrics.
# ==============================================================================

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

# 1. Configuration & Argument Parsing
REPEATS=1
CATEGORY=""
DIFFICULTY=""
DRY_RUN_FLAG="--dry-run"
LIVE_MODE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --repeats|-r)
      REPEATS="$2"
      shift 2
      ;;
    --category|-c)
      CATEGORY="$2"
      shift 2
      ;;
    --difficulty|-d)
      DIFFICULTY="$2"
      shift 2
      ;;
    --live)
      LIVE_MODE=true
      DRY_RUN_FLAG=""
      shift
      ;;
    --dry-run)
      DRY_RUN_FLAG="--dry-run"
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [--repeats N] [--category CAT] [--difficulty DIFF] [--live] [--dry-run]"
      echo "  --repeats N      Number of evaluation runs per task (default: 1)"
      echo "  --category CAT   Filter tasks (bug_fix, feature, testing, migration)"
      echo "  --difficulty DIF Filter difficulty (easy, medium, hard)"
      echo "  --live           Run against live Gemini / OpenCode backend"
      echo "  --dry-run        Run in simulated/mock mode (default for offline evaluation)"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Resolve harness binary
if [ -f ".venv/bin/harness" ]; then
    HARNESS_BIN=".venv/bin/harness"
elif command -v harness &>/dev/null; then
    HARNESS_BIN="harness"
else
    echo "ERROR: 'harness' binary not found. Please activate your virtual environment or run ./scripts/setup.sh"
    exit 1
fi

echo "=================================================================="
echo " ADAPTIVE CODING AGENT HARNESS — EXPERIMENTAL EVALUATION SUITE   "
echo "=================================================================="
echo "Configuration: Repeats=$REPEATS | Mode=$([ "$LIVE_MODE" = true ] && echo 'LIVE (Gemini/OpenCode)' || echo 'OFFLINE / SIMULATED') | Category=${CATEGORY:-all} | Difficulty=${DIFFICULTY:-all}"
echo "Start Time: $(date)"

# 2. Environment Validation
echo ""
echo "[1/7] Validating Environment..."
if [ "$LIVE_MODE" = true ]; then
    if [ -z "${GEMINI_API_KEY:-}" ]; then
        echo "WARNING: GEMINI_API_KEY is not set in environment! Live calls may fail."
        echo "To run offline simulated benchmark without credentials, omit --live flag."
    else
        echo "  ✓ GEMINI_API_KEY detected"
    fi
    if command -v opencode &>/dev/null; then
        echo "  ✓ OpenCode binary found: $(command -v opencode)"
    else
        echo "  WARNING: 'opencode' command not found in PATH."
    fi
else
    echo "  ✓ Running in offline reproducible mode (no external network or LLM API keys required)"
fi

# Ensure output directories exist
mkdir -p results/raw results/reports results/plots reports

# Build filter arguments
EXTRA_ARGS=()
if [ -n "$CATEGORY" ]; then
    EXTRA_ARGS+=(--category "$CATEGORY")
fi
if [ -n "$DIFFICULTY" ]; then
    EXTRA_ARGS+=(--difficulty "$DIFFICULTY")
fi

# 3. Step 1: Baseline Experiment (Minimal Scaffolding)
echo ""
echo "[2/7] Running Experiment A: Baseline (OpenCode + Gemini, single-turn, no feedback)..."
"$HARNESS_BIN" benchmark --config baseline --repeats "$REPEATS" $DRY_RUN_FLAG "${EXTRA_ARGS[@]}"

# 4. Step 2: Ablation B: Repository Context
echo ""
echo "[3/7] Running Experiment B: Ablation — Repository Context Only..."
"$HARNESS_BIN" benchmark --config repo-context --repeats "$REPEATS" $DRY_RUN_FLAG "${EXTRA_ARGS[@]}"

# 5. Step 3: Ablation C: Test Feedback Loop
echo ""
echo "[4/7] Running Experiment C: Ablation — Test Feedback Loop (multi-turn self-correction)..."
"$HARNESS_BIN" benchmark --config test-feedback --repeats "$REPEATS" $DRY_RUN_FLAG "${EXTRA_ARGS[@]}"

# 6. Step 4: Ablation D: Specialized Agent Modes
echo ""
echo "[5/7] Running Experiment D: Ablation — Specialized Agent Modes..."
"$HARNESS_BIN" benchmark --config specialized-agent --repeats "$REPEATS" $DRY_RUN_FLAG "${EXTRA_ARGS[@]}"

# 7. Step 5: Full Harness Experiment (Context + Specialized Mode + Feedback Loop + Worktrees)
echo ""
echo "[6/7] Running Experiment E: Full Adaptive Harness (All Scaffolding Enabled)..."
"$HARNESS_BIN" benchmark --config full-harness --repeats "$REPEATS" $DRY_RUN_FLAG "${EXTRA_ARGS[@]}"

# 8. Step 6: Generate Comparative Metrics & Scientific Report
echo ""
echo "[7/7] Generating Benchmark Comparison and Evaluation Reports..."
"$HARNESS_BIN" compare --baseline baseline --candidate full-harness
"$HARNESS_BIN" report

echo ""
echo "=================================================================="
echo " EXPERIMENT EXECUTION COMPLETE!                                   "
echo "=================================================================="
echo "Run database: runs.db"
echo "Markdown & JSON reports saved to:"
echo "  - results/reports/"
echo "  - reports/"
echo "To explore runs interactively in the Web Dashboard, execute:"
echo "  $HARNESS_BIN dashboard --port 8000"
echo "=================================================================="
