# Evaluation Methodology & Benchmark Specification

The **Adaptive Coding Agent Harness** implements an empirical evaluation framework designed to answer:
> *"How much does scaffolding improve the performance of the same underlying coding agent?"*

---

## 1. Evaluation States

Unlike naive evaluations that equate "agent produced some edits" with success, the harness enforces a strict 3-tier status hierarchy:

```text
SUCCESS:
  All required public validation tests pass
  AND post-loop hidden regression tests pass
  AND no critical execution error or unhandled exceptions occur
  AND repository remains in a valid syntax/build state

PARTIAL:
  Public validation tests pass
  BUT hidden edge-case validation tests fail
  (Identifies "gaming" or superficial implementations that miss general correctness)

FAILURE:
  Required public validation fails
  OR agent crashes or raises unhandled errors
  OR execution times out
  OR iteration limit is reached without resolution
```

---

## 2. Public vs. Hidden Validation Strategy

To evaluate genuine generalization rather than overfitting or gaming:
* **Public Tests**: Visible within the repository. The agent can see these tests or infer requirements from them.
* **Hidden Tests**: Located in independent test suites (`tests/test_hidden.py`, `test_hidden.js`) executed strictly by the evaluation controller **after the agent loop concludes**.
* The agent is never exposed to hidden test code or assertions during its iterations.

---

## 3. 30-Task Benchmark Suite

The benchmark contains **30 curated tasks** partitioned across 4 real-world software engineering domains and 3 difficulty tiers:

| Category | Count | Repositories | Key Problem Types |
| :--- | :---: | :--- | :--- |
| **Bug Fixes** | 10 | `fastapi_app`, `python_cli`, `node_app` | HTTP status codes, missing field validation, off-by-one errors, CSV delimiter handling, state mutation bugs, null/undefined crashes. |
| **Feature Additions** | 10 | `fastapi_app`, `python_cli`, `node_app` | New REST endpoints, CLI flags/subcommands, filtering/sorting queries, token authentication, configuration parsing. |
| **Test Writing** | 5 | `fastapi_app`, `python_cli`, `node_app` | Edge-case unit tests, API failure test cases, regression coverage, boundary value tests. |
| **Code Migrations** | 5 | `fastapi_app`, `python_cli`, `node_app` | Deprecated library migration, schema upgrades, framework pattern modernizations. |

### Difficulty Distribution
* **Easy (10 tasks)**: Direct, localized modifications (e.g. adding a status code check or simple parameter).
* **Medium (14 tasks)**: Multi-step logic, input sanitization, error propagation across modules.
* **Hard (6 tasks)**: Subtle state management, cross-module refactoring, edge-case validation with hidden constraints.

---

## 4. Quantitative Metrics

### Primary Metrics
* **Success Rate (%)**: $\frac{\text{Runs with Status == SUCCESS}}{\text{Total Runs}} \times 100\%$
* **Partial Success Rate (%)**: $\frac{\text{Runs with Status == PARTIAL}}{\text{Total Runs}} \times 100\%$
* **Test Pass Rate (%)**: Percentage of runs whose public test suite finished with exit code 0.
* **Absolute Success Delta**: $\text{Success}_{\text{Harness}} - \text{Success}_{\text{Baseline}}$ (in percentage points).
* **Relative Success Delta**: $\frac{\text{Success}_{\text{Harness}} - \text{Success}_{\text{Baseline}}}{\text{Success}_{\text{Baseline}}} \times 100\%$.

### Execution & Efficiency Metrics
* **Timing Breakdown**:
  * `agent_time_seconds`: Total time spent in LLM inference and agent tool dispatch.
  * `test_time_seconds`: Time spent executing automated test suites.
  * `feedback_time_seconds`: Time spent parsing tracebacks and constructing remediation prompts.
  * `total_time_seconds`: Overall end-to-end wall-clock time.
* **Iteration Count**: Mean and median cycles required to reach passing status (1 = zero-shot, 2–5 = self-corrected).
* **Token Usage & Cost**:
  * Input tokens (context + task + feedback)
  * Output tokens (code generation)
  * Total tokens per successful task
  * Tokens per attempt

---

## 5. Failure Taxonomy

Failed executions are classified into 12 distinct root-cause categories by `FeedbackAnalyzer`:
1. `syntax_error`: Python/JS indentation, unclosed delimiters, or invalid syntax.
2. `compile_error`: Build failures or type check errors.
3. `test_failure`: Explicit assertion failure in test runner.
4. `lint_failure`: Linter violation (Ruff / ESLint / Flake8).
5. `dependency_error`: Missing package or unresolvable import.
6. `wrong_implementation`: Logic error or unexpected return value.
7. `context_failure`: Agent misunderstood repository layout or architecture.
8. `tool_failure`: Invalid tool call or unhandled command error.
9. `timeout`: Execution exceeded the configured time limit.
10. `permission_failure`: Shell command or path access blocked by security policy.
11. `environment_error`: System or runtime environment issue.
12. `unknown`: Unclassified failure.
