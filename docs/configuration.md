# Configuration Specification

The Adaptive Coding Agent Harness supports both environment-level defaults and experiment-specific YAML configurations.

## Environment Variables (`.env`)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | *None* | Google Gemini API Key. If unset, `--dry-run` mock mode is recommended. |
| `GEMINI_MODEL` | `google/gemini-2.5-flash` | Gemini model ID used by OpenCode. |
| `OPENCODE_COMMAND` | `opencode` | Path or name of the OpenCode executable. |
| `MAX_ITERATIONS` | `5` | Maximum self-correction iterations per task. |
| `COMMAND_TIMEOUT` | `120` | Subprocess command timeout in seconds. |
| `TEST_TIMEOUT` | `120` | Test suite execution timeout in seconds. |
| `WORKSPACE_ROOT` | `./workspace` | Directory where isolated benchmark worktrees are generated. |
| `LOG_LEVEL` | `INFO` | Logger verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `DB_PATH` | `./runs.db` | Path to SQLite database for run records. |

## Experiment Configurations (`configs/*.yaml`)

Example: `configs/developer.yaml` (Full Harness):

```yaml
name: full-harness

agent:
  mode: developer
  temperature: 0.2

context:
  repository_summary: true
  git_status: true
  directory_tree: true

tools:
  filesystem:
    read: true
    write: true
  terminal:
    enabled: true
  git:
    read: true
    write: false
  tests:
    enabled: true
  linter:
    enabled: true

feedback:
  tests: true
  linter: true

max_iterations: 5
```

Example: `configs/baseline.yaml` (Minimally Scaffolded Baseline):

```yaml
name: baseline

agent:
  mode: developer
  temperature: 0.2

context:
  repository_summary: false
  git_status: false
  directory_tree: false

tools:
  filesystem:
    read: true
    write: true
  terminal:
    enabled: true
  git:
    read: true
    write: false
  tests:
    enabled: false
  linter:
    enabled: false

feedback:
  tests: false
  linter: false

max_iterations: 1
```

## Tool Security Configuration

The harness enforces security controls on the agent:
- Blocks commands matching patterns: `rm -rf /`, `mkfs`, `fdisk`, `dd`, `chmod 777 /`, `git push`.
- Validates file paths to ensure reading and writing remain strictly bounded within the designated workspace directory.
