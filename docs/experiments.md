# Experiments, Ablation Studies & Research Questions

## 1. Core Research Questions

The experimental framework investigates five specific research questions:

* **RQ1: Feedback Scaffolding** — *Does automated test failure feedback significantly improve task completion over single-turn execution?*
* **RQ2: Context Grounding** — *Does injecting repository architecture, file hierarchies, and Git status improve accuracy or reduce hallucination?*
* **RQ3: Specialized Agent Modes** — *Do domain-focused system prompts (Developer, Test Writer, Migration) outperform generic prompts on category-specific tasks?*
* **RQ4: Cost & Resource Overhead** — *What is the resource trade-off (wall-clock time, token consumption, cost) required to achieve higher success rates?*
* **RQ5: Error Recovery Distribution** — *Which categories of software engineering bugs (e.g., assertion mismatches, edge cases, validation) benefit most from iterative remediation?*

---

## 2. Experimental Configurations Matrix

| ID | Name | Repo Context | Agent Mode | Tool Permissions | Test Feedback | Max Iterations |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **A** | **Baseline** | Disabled | Developer | Read/Write/Term | None (Single Turn) | 1 |
| **B** | **Repo Context** | Enabled | Developer | Read/Write/Term | None (Single Turn) | 1 |
| **C** | **Test Feedback** | Disabled | Developer | Read/Write/Term | Automated Loop | 5 |
| **D** | **Specialized Agent**| Disabled | Dynamic Mode | Read/Write/Term | None (Single Turn) | 1 |
| **E** | **Full Harness** | Enabled | Dynamic Mode | Guardrailed | Tests + Linters | 5 |

---

## 3. Controlling Variance & Reproducibility

Agent behavior can vary across trials due to model temperature and token sampling. To address this:
1. **Repeated Runs (`--repeats N`)**:
   Runs each benchmark task $N$ times across isolated worktrees.
   ```bash
   harness benchmark --config baseline --repeats 3
   harness benchmark --config full-harness --repeats 3
   ```
2. **Statistical Aggregation**:
   The metrics engine calculates:
   * Success rate mean and test pass rate mean
   * Mean and median wall-clock durations
   * Mean and median iteration counts
   * Duration standard deviation and variance (when $N \ge 2$)
   * Total and average token consumption per completed task
3. **Traceability**:
   Every run record in `runs.db` captures model name, timestamp, temperature setting, Git commit hash, task ID, and timing breakdown (`agent_time`, `test_time`, `feedback_time`).

---

## 4. Reproducing the Complete Experiment Suite

Execute all ablation configurations and generate comparative reports with a single command:

```bash
# Run complete reproducible suite (offline simulated mode)
./scripts/run_experiment.sh --repeats 1

# Run with 3 repetitions per task
./scripts/run_experiment.sh --repeats 3

# Run against live Gemini + OpenCode backend
export GEMINI_API_KEY="your-api-key"
./scripts/run_experiment.sh --live --repeats 3
```

Results are saved to:
* `results/reports/comparison_baseline_vs_full-harness_<timestamp>.md`
* `results/reports/comparison_baseline_vs_full-harness_<timestamp>.json`
* SQLite database: `runs.db`
