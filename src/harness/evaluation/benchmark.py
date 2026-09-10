"""Benchmark suite runner with isolated repository worktrees and difficulty grading."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import yaml
from rich.console import Console
from rich.table import Table

from harness.config import HarnessConfig, get_settings
from harness.evaluation.metrics import BenchmarkMetrics, MetricsCalculator
from harness.feedback.loop import FeedbackLoopController
from harness.logging_config import logger
from harness.models import RunRecord, Task
from harness.opencode.base import AgentBackend
from harness.storage.database import RunDatabase


class BenchmarkRunner:
    """Orchestrates multi-task benchmark executions over isolated repositories."""

    def __init__(
        self,
        repositories_dir: Path = Path("benchmark/repositories"),
        tasks_dir: Path = Path("benchmark/tasks"),
        db: Optional[RunDatabase] = None,
    ):
        self.repositories_dir = repositories_dir.resolve()
        self.tasks_dir = tasks_dir.resolve()
        self.db = db or RunDatabase(get_settings().db_path)
        self.console = Console()

    def load_tasks(
        self,
        category: Optional[str] = None,
        difficulty: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> List[Task]:
        """Discover and load all task YAML files."""
        tasks: List[Task] = []
        if not self.tasks_dir.exists():
            logger.warning(f"Tasks directory '{self.tasks_dir}' does not exist")
            return []

        for yaml_path in sorted(self.tasks_dir.glob("**/*.yaml")):
            try:
                with open(yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if not isinstance(data, dict):
                    continue
                task = Task(**data)
                if category and task.category != category:
                    continue
                if difficulty and task.difficulty.lower() != difficulty.lower():
                    continue
                if task_id and task.id != task_id:
                    continue
                tasks.append(task)
            except Exception as e:
                logger.error(f"Error loading task file {yaml_path.name}: {e}")

        return tasks

    def apply_setup_action(self, workspace: Path, action: Optional[str]) -> None:
        """Inject the defect or requirement state into the isolated worktree."""
        if not action:
            return

        main_py = workspace / "app" / "main.py"
        cli_parser = workspace / "cli" / "parser.py"
        cli_formatter = workspace / "cli" / "formatter.py"
        cli_commands = workspace / "cli" / "commands.py"
        node_index = workspace / "index.js"

        if action == "inject_login_500" and main_py.exists():
            content = main_py.read_text(encoding="utf-8")
            main_py.write_text(content.replace("status_code=401", "status_code=500"), encoding="utf-8")
        elif action == "remove_password_check" and main_py.exists():
            content = main_py.read_text(encoding="utf-8")
            main_py.write_text(content.replace("if not req.password:", "if False:"), encoding="utf-8")
        elif action == "allow_blank_title" and main_py.exists():
            content = main_py.read_text(encoding="utf-8")
            main_py.write_text(content.replace("if not item.title.strip():", "if False:"), encoding="utf-8")
        elif action == "remove_json_error_handling" and cli_parser.exists():
            content = cli_parser.read_text(encoding="utf-8")
            cli_parser.write_text(content.replace("except json.JSONDecodeError as e:", "except (AttributeError, KeyError) as e:"), encoding="utf-8")
        elif action == "remove_empty_array_check" and node_index.exists():
            content = node_index.read_text(encoding="utf-8")
            node_index.write_text(content.replace("if (numbers.length === 0)", "if (false)"), encoding="utf-8")
        elif action == "remove_leading_query_strip" and node_index.exists():
            content = node_index.read_text(encoding="utf-8")
            node_index.write_text(content.replace('qs.startsWith("?") ? qs.slice(1) : qs', 'qs'), encoding="utf-8")
        elif action == "remove_item_404" and main_py.exists():
            content = main_py.read_text(encoding="utf-8")
            main_py.write_text(content.replace("if item_id not in ITEMS_DB:", "if False:"), encoding="utf-8")
        elif action == "break_key_value_trim" and cli_parser.exists():
            content = cli_parser.read_text(encoding="utf-8")
            cli_parser.write_text(content.replace("k.strip()] = v.strip()", "k] = v"), encoding="utf-8")
        elif action == "remove_type_check" and node_index.exists():
            content = node_index.read_text(encoding="utf-8")
            node_index.write_text(content.replace("if (!Array.isArray(numbers))", "if (false)"), encoding="utf-8")
        elif action == "break_csv_empty" and cli_formatter.exists():
            content = cli_formatter.read_text(encoding="utf-8")
            cli_formatter.write_text(content.replace("if not items:\n            return []", "if not items:\n            return None"), encoding="utf-8")
        elif action == "remove_pagination" and main_py.exists():
            content = main_py.read_text(encoding="utf-8")
            main_py.write_text(content.replace("return items[skip : skip + limit]", "return items\n"), encoding="utf-8")
        elif action == "stub_status_command" and cli_commands.exists():
            content = cli_commands.read_text(encoding="utf-8")
            cli_commands.write_text(content.replace('return {"status": "active", "version": "1.0.0"}', 'raise NotImplementedError("status")'), encoding="utf-8")
        elif action == "stub_csv_formatter" and cli_formatter.exists():
            content = cli_formatter.read_text(encoding="utf-8")
            cli_formatter.write_text(content.replace("return lines", 'raise NotImplementedError("csv")'), encoding="utf-8")
        elif action == "stub_root_endpoint" and main_py.exists():
            content = main_py.read_text(encoding="utf-8")
            main_py.write_text(content.replace('return {"status": "ok", "service": "TaskFlow"}', 'raise HTTPException(status_code=503)'), encoding="utf-8")
        elif action == "stub_query_parser" and node_index.exists():
            content = node_index.read_text(encoding="utf-8")
            node_index.write_text(content.replace("return params;", "return {};"), encoding="utf-8")
        elif action == "stub_item_create" and main_py.exists():
            content = main_py.read_text(encoding="utf-8")
            main_py.write_text(content.replace("return new_item", "raise HTTPException(status_code=500)"), encoding="utf-8")
        elif action == "stub_command_dispatcher" and cli_commands.exists():
            content = cli_commands.read_text(encoding="utf-8")
            cli_commands.write_text(content.replace("return self.formatter.to_json", "raise NotImplementedError"), encoding="utf-8")
        elif action == "stub_calculate_metrics" and node_index.exists():
            content = node_index.read_text(encoding="utf-8")
            node_index.write_text(content.replace("return {", "throw new Error('Not implemented'); return {"), encoding="utf-8")
        elif action == "stub_login_token" and main_py.exists():
            content = main_py.read_text(encoding="utf-8")
            main_py.write_text(content.replace('"token": f"mock_token_{req.username}", ', ''), encoding="utf-8")
        elif action == "stub_json_parser" and cli_parser.exists():
            content = cli_parser.read_text(encoding="utf-8")
            cli_parser.write_text(content.replace("return json.loads(raw)", "raise NotImplementedError"), encoding="utf-8")

    def prepare_isolated_workspace(self, task: Task) -> Path:
        """Create a clean copy of the task repository in an isolated worktree with initial defect state."""
        src_repo = self.repositories_dir / task.repository
        if not src_repo.exists():
            raise FileNotFoundError(f"Source repository '{task.repository}' not found at {src_repo}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        workspace = Path(get_settings().workspace_root) / f"{task.id}_{timestamp}"
        workspace.mkdir(parents=True, exist_ok=True)

        # Copy repository files
        shutil.copytree(
            src_repo,
            workspace,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".venv", "venv", "__pycache__", ".git", "node_modules"),
        )

        # Apply initial defect action
        self.apply_setup_action(workspace, task.setup_action)

        # Initialize clean git repo inside isolated workspace
        subprocess.run(["git", "init", "-q"], cwd=str(workspace), check=False)
        subprocess.run(["git", "config", "user.name", "BenchmarkRunner"], cwd=str(workspace), check=False)
        subprocess.run(["git", "config", "user.email", "benchmark@harness.local"], cwd=str(workspace), check=False)
        subprocess.run(["git", "add", "-A"], cwd=str(workspace), check=False)
        subprocess.run(["git", "commit", "-m", f"Initial defect state for {task.id}", "-q"], cwd=str(workspace), check=False)

        return workspace

    def run_task(
        self,
        task: Task,
        config: HarnessConfig,
        backend: AgentBackend,
    ) -> RunRecord:
        """Execute a single benchmark task in an isolated workspace."""
        workspace = self.prepare_isolated_workspace(task)
        try:
            controller = FeedbackLoopController(
                task=task,
                workspace=workspace,
                config=config,
                backend=backend,
            )
            record = controller.execute()
            self.db.save_run(record)
            return record
        finally:
            try:
                shutil.rmtree(workspace, ignore_errors=True)
            except Exception:
                pass

    def run_suite(
        self,
        tasks: List[Task],
        config: HarnessConfig,
        backend: AgentBackend,
        repeats: int = 1,
    ) -> BenchmarkMetrics:
        """Execute tasks (optionally repeated) in the benchmark suite and compute metrics."""
        total_runs_count = len(tasks) * repeats
        self.console.print(f"\n[bold blue]Starting Benchmark Suite: {config.name}[/bold blue]")
        self.console.print(
            f"Tasks: {len(tasks)} | Repeats: {repeats} | Total Executions: {total_runs_count} | "
            f"Model: {config.model or 'default'} | Feedback: {config.feedback.tests}\n"
        )

        runs: List[RunRecord] = []
        exec_index = 0

        for r in range(1, repeats + 1):
            repeat_prefix = f"[Repeat {r}/{repeats}] " if repeats > 1 else ""
            for task in tasks:
                exec_index += 1
                self.console.print(
                    f"[bold cyan][{exec_index}/{total_runs_count}][/bold cyan] {repeat_prefix}"
                    f"Running [yellow]{task.id}[/yellow] ({task.difficulty}) - {task.title}"
                )
                record = self.run_task(task, config, backend)
                runs.append(record)

                status_color = "green" if record.success else ("yellow" if record.status.value == "PARTIAL" else "red")
                self.console.print(
                    f"       Result: [{status_color}]{record.status.value}[/{status_color}] | "
                    f"Iterations: {record.iteration_count} | Duration: {record.duration_seconds}s\n"
                )

        metrics = MetricsCalculator.compute(runs, config_name=config.name)
        self.print_summary_table(metrics)
        return metrics

    def print_summary_table(self, metrics: BenchmarkMetrics) -> None:
        """Print a rich terminal summary table of benchmark results."""
        table = Table(title=f"Benchmark Results: {metrics.config_name}")
        table.add_column("Metric", style="cyan", justify="left")
        table.add_column("Value", style="magenta", justify="right")

        table.add_row("Total Executions", str(metrics.total_tasks))
        table.add_row("Successful Tasks", str(metrics.successful_tasks))
        table.add_row("Partial Successes", str(metrics.partial_tasks))
        table.add_row("Failed Tasks", str(metrics.failed_tasks))
        table.add_row("Success Rate", f"{metrics.success_rate:.1f}%")
        table.add_row("Test Pass Rate", f"{metrics.test_pass_rate:.1f}%")
        table.add_row("Avg Time", f"{metrics.avg_duration_seconds:.1f}s")
        table.add_row("Avg Iterations", f"{metrics.avg_iterations:.2f}")

        if metrics.tokens_available and metrics.avg_tokens_per_task:
            table.add_row("Avg Tokens / Task", f"{metrics.avg_tokens_per_task:,}")
            table.add_row("Total Tokens", f"{metrics.total_tokens:,}")
        else:
            table.add_row("Token Usage", "unavailable")

        self.console.print(table)
