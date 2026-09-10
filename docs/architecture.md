# Architecture Specification: Adaptive Coding Agent Harness

The **Adaptive Coding Agent Harness** is an orchestration, scaffolding, and evaluation framework designed around OpenCode running on Google Gemini. Rather than implementing an IDE or LLM from scratch, the harness wraps the autonomous coding agent with engineering guardrails, repository context, specialized modes, permission policies, test/linter feedback loops, and automated benchmarking.

## System Architecture Diagram

```text
                               +-----------------------------+
                               |            USER             |
                               +--------------+--------------+
                                              |
                                              v
                              +-------------------------------+
                              |    CLI Interface / REST API   |
                              |   (Typer & FastAPI Dashboard) |
                              +---------------+---------------+
                                              |
                                              v
                              +-------------------------------+
                              |         Task Manager          |
                              |  (Isolated Worktree Sandbox)  |
                              +---------------+---------------+
                                              |
                                              v
                              +-------------------------------+
                              |    Agent Scaffolding Engine   |
                              |  (Context, Modes, Permissions)|
                              +---------------+---------------+
                                              |
                                              v
                              +-------------------------------+
                              |         AgentBackend          |
                              |  +-------------------------+  |
                              |  | OpenCodeBackend (Real)  |  |
                              |  | MockBackend (Simulated) |  |
                              |  +-------------------------+  |
                              +---------------+---------------+
                                              |
                                              v
                              +-------------------------------+
                              |     OpenCode 1.18.30 +        |
                              |       Google Gemini           |
                              +---------------+---------------+
                                              |
                     +------------------------+-----------------------+
                     |                        |                       |
                     v                        v                       v
               Filesystem Read/Edit     Bash Terminal Execution     Safe Git
                     |                        |                       |
                     +------------------------+-----------------------+
                                              |
                                              v
                              +-------------------------------+
                              |   Automated Test & Linter     |
                              |  (pytest, node test, ruff)    |
                              +---------------+---------------+
                                              |
                                              v
                              +-------------------------------+
                              |        Feedback Engine        |
                              |   (Failure Analysis & Prompt) |
                              +---------------+---------------+
                                              |
                                     tests failed?
                                       /         \
                                     YES          NO
                                      |            |
                                      v            v
                               Send feedback    SUCCESS
                               to agent turn       |
                                      |            v
                                      +----> Persistence & Metrics
                                                   |
                                     +-------------+-------------+
                                     |             |             |
                                     v             v             v
                                Success Rate  Token Usage  Duration/Diff
```

## Core Components

### 1. Agent Controller & Scaffolding Layer
- **Repository Context Inspector**: Inspects languages, package managers, framework, Git dirty status, and directory layout, generating a compact context summary without bloating the token context.
- **Specialized Agent Modes**:
  - `DeveloperMode`: Full lifecycle implementation, refactoring, and test/linter verification.
  - `TestWriterMode`: Analyzes public APIs and failure modes to craft robust test suites.
  - `MigrationMode`: Audits package manifests for version upgrades, deprecations, and breaking changes.
- **Tool Permission Engine**: Enforces strict security boundaries (blocking `rm -rf /`, `mkfs`, credential file access, workspace escapes, and unauthorized `git push`).

### 2. OpenCode Adapter & Dual-Backend Interface
- **`AgentBackend` Abstract Class**: Decouples execution strategy from the evaluation loop.
- **`OpenCodeBackend`**: Invokes the official OpenCode CLI (`opencode run --format json --dir <workspace> -m google/gemini-2.5-flash --auto`), parsing newline-delimited JSON stream events and querying `opencode export <session_id>` for exact token counts.
- **`MockBackend`**: Deterministic, offline simulation engine enabling reproducible unit tests, integration tests, and interview demonstrations without external API quotas.

### 3. Verification & Self-Correction Feedback Loop
The central engine of the harness:
1. Agent generates code modifications in the workspace.
2. The harness immediately triggers the target test runner (`pytest`, `node:test`, etc.).
3. If failures occur, `FeedbackAnalyzer` parses failure tracebacks, error types, and assertion mismatches, generating a structured remediation prompt.
4. The agent receives this actionable feedback and adjusts implementation across iterative turns (up to `MAX_ITERATIONS`).
5. Halts immediately upon test pass or when reaching the iteration threshold.

### 4. Storage & Evaluation Engine
- **SQLite Database (`runs.db`)**: Records run IDs (`run_YYYYMMDD_HHMMSS`), task metadata, duration, iterations, success flags, token usage, tool call counts, failure categories, and Git diff statistics.
- **Metrics Calculator**: Aggregates primary (Success Rate, Test Pass Rate) and secondary metrics (Average Time, Token Cost, Failure Taxonomy).
- **Comparison & Ablation Reporter**: Outputs structured Markdown and JSON comparison reports.
