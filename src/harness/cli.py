"""Command Line Interface for Adaptive Coding Agent Harness."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from harness.config import HarnessConfig, get_settings
from harness.evaluation.benchmark import BenchmarkRunner
from harness.evaluation.metrics import MetricsCalculator
from harness.evaluation.reporter import ComparisonReporter
from harness.feedback.loop import FeedbackLoopController
from harness.models import AgentMode, EvaluationStatus, Task
from harness.opencode import get_backend
from harness.storage.database import RunDatabase

app = typer.Typer(
    name="harness",
    help="Adaptive Coding Agent Harness around OpenCode + Gemini",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print("Adaptive Coding Agent Harness [bold cyan]v0.2.0[/bold cyan]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
):
    """Adaptive Coding Agent Harness around OpenCode + Gemini."""
    pass


@app.command("run")
def run_task(
    repo: str = typer.Option(..., "--repo", "-r", help="Path to target repository"),
    task: Optional[str] = typer.Option(None, "--task", "-t", help="Task description prompt"),
    task_file: Optional[str] = typer.Option(None, "--task-file", "-f", help="Path to markdown/YAML task description"),
    mode: str = typer.Option("developer", "--mode", "-m", help="Agent mode: developer | test_writer | migration"),
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="Path to Harness YAML configuration"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run with simulated mock agent (no API credentials needed)"),
    model: Optional[str] = typer.Option(None, "--model", help="Gemini model override (e.g. google/gemini-2.5-flash)"),
):
    """Execute a single coding task against a repository with adaptive feedback."""
    repo_path = Path(repo).resolve()
    if not repo_path.exists():
        console.print(f"[bold red]Error:[/bold red] Repository path '{repo}' does not exist.")
        raise typer.Exit(1)

    # Load task description
    task_title = "Ad-hoc task"
    task_desc = ""
    test_cmd = "pytest -q"

    if task_file:
        t_path = Path(task_file)
        if not t_path.exists():
            console.print(f"[bold red]Error:[/bold red] Task file '{task_file}' does not exist.")
            raise typer.Exit(1)
        content = t_path.read_text(encoding="utf-8")
        task_title = t_path.stem
        task_desc = content
    elif task:
        task_title = task[:50]
        task_desc = task
    else:
        console.print("[bold red]Error:[/bold red] Either --task or --task-file must be provided.")
        raise typer.Exit(1)

    # Load harness configuration
    if config_file and Path(config_file).exists():
        cfg = HarnessConfig.from_yaml(config_file)
    else:
        cfg = HarnessConfig()

    cfg.agent.mode = AgentMode(mode.lower())
    if model:
        cfg.model = model
    if dry_run:
        cfg.dry_run = True

    # Header display
    console.print(Panel.fit(
        f"[bold cyan]Adaptive Coding Agent Harness[/bold cyan]\n"
        f"Task: [yellow]{task_title}[/yellow]\n"
        f"Repository: [blue]{repo_path.name}[/blue] | Mode: [magenta]{cfg.agent.mode.value}[/magenta] | "
        f"Model: [green]{cfg.model or get_settings().gemini_model}[/green]\n"
        f"Feedback Loop: [green]{'ENABLED' if cfg.feedback.tests else 'DISABLED'}[/green] | "
        f"Dry-Run: [yellow]{'YES' if cfg.dry_run else 'NO'}[/yellow]",
        border_style="cyan",
    ))

    # Initialize backend
    backend = get_backend(
        opencode_cmd=get_settings().opencode_command,
        model=cfg.model or get_settings().gemini_model,
        dry_run=cfg.dry_run,
    )

    task_obj = Task(
        id=f"adhoc_{repo_path.name}",
        title=task_title,
        repository=repo_path.name,
        description=task_desc,
        expected_behavior="Pass automated tests and adhere to requirements",
        test_command=test_cmd,
    )

    controller = FeedbackLoopController(
        task=task_obj,
        workspace=repo_path,
        config=cfg,
        backend=backend,
    )

    console.print("[dim][1/5] Initializing agent...[/dim]")
    console.print("[dim][2/5] Inspecting repository...[/dim]")
    console.print("[dim][3/5] Implementing changes...[/dim]")
    console.print("[dim][4/5] Running tests...[/dim]")
    console.print("[dim][5/5] Evaluating result...[/dim]\n")

    record = controller.execute()

    # Save to database
    db = RunDatabase(get_settings().db_path)
    db.save_run(record)

    # Status summary
    status_color = "bold green" if record.status == EvaluationStatus.SUCCESS else ("bold yellow" if record.status == EvaluationStatus.PARTIAL else "bold red")
    console.print(f"[{status_color}]STATUS: {record.status.value}[/{status_color}]")
    console.print(f"Iterations: {record.iteration_count}/{cfg.max_iterations} | Duration: {record.duration_seconds}s")
    if record.git_diff_summary:
        console.print(f"Changes: {record.git_diff_summary}")

    if not record.success and record.failure_reason:
        console.print(f"[red]Failure Reason: {record.failure_reason}[/red]")


def resolve_config_path(config: str) -> Path:
    """Resolve config name or path to an existing Path."""
    p = Path(config)
    if p.exists():
        return p
    for candidate in [
        Path("configs") / f"{config}.yaml",
        Path("configs") / f"{config.replace('-', '_')}.yaml",
        Path("configs") / config,
    ]:
        if candidate.exists():
            return candidate
    return p


@app.command("benchmark")
def run_benchmark(
    config: str = typer.Option("configs/developer.yaml", "--config", "-c", help="Path to config YAML or preset name"),
    category: Optional[str] = typer.Option(None, "--category", help="Filter tasks by category (bug_fix, feature, testing, migration)"),
    difficulty: Optional[str] = typer.Option(None, "--difficulty", help="Filter tasks by difficulty (easy, medium, hard)"),
    task_id: Optional[str] = typer.Option(None, "--task-id", help="Filter to a specific task ID"),
    repeats: int = typer.Option(1, "--repeats", "-r", help="Number of repetitions per task for variance measurement"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run in mock mode without Gemini API calls"),
    model: Optional[str] = typer.Option(None, "--model", help="Gemini model override"),
):
    """Execute benchmark suite over isolated repository workspaces."""
    cfg_path = resolve_config_path(config)
    if not cfg_path.exists():
        console.print(f"[bold red]Error:[/bold red] Configuration file '{config}' not found.")
        raise typer.Exit(1)

    cfg = HarnessConfig.from_yaml(cfg_path)
    if dry_run:
        cfg.dry_run = True
    if model:
        cfg.model = model

    runner = BenchmarkRunner()
    tasks = runner.load_tasks(category=category, difficulty=difficulty, task_id=task_id)

    if not tasks:
        console.print("[bold red]Error:[/bold red] No matching tasks found in benchmark/tasks.")
        raise typer.Exit(1)

    backend = get_backend(
        opencode_cmd=get_settings().opencode_command,
        model=cfg.model or get_settings().gemini_model,
        dry_run=cfg.dry_run,
    )

    runner.run_suite(tasks=tasks, config=cfg, backend=backend, repeats=repeats)


@app.command("compare")
def compare_runs(
    baseline: str = typer.Option(..., "--baseline", "-b", help="Baseline configuration name (e.g. baseline)"),
    candidate: str = typer.Option(..., "--candidate", "-c", help="Candidate configuration name (e.g. full-harness)"),
):
    """Generate comparative markdown and JSON reports between baseline and harness configurations."""
    db = RunDatabase(get_settings().db_path)
    reporter = ComparisonReporter(db)

    res = reporter.generate_comparison(baseline, candidate)
    console.print(Panel.fit(
        f"[bold green]Comparison Report Generated[/bold green]\n"
        f"Markdown: [cyan]{res['markdown_path']}[/cyan]\n"
        f"JSON: [cyan]{res['json_path']}[/cyan]",
        border_style="green",
    ))
    console.print(res["markdown"])


@app.command("report")
def generate_ablation_report(
    configs: str = typer.Option("baseline,repo-context,test-feedback,specialized-agent,full-harness", "--configs", help="Comma-separated configuration names"),
):
    """Generate multi-configuration ablation summary report."""
    db = RunDatabase(get_settings().db_path)
    reporter = ComparisonReporter(db)
    cfg_list = [c.strip() for c in configs.split(",") if c.strip()]
    table_md = reporter.generate_ablation_table(cfg_list)
    console.print(table_md)


@app.command("demo")
def run_demo(
    dry_run: bool = typer.Option(True, "--dry-run/--real", help="Use mock backend or live Gemini API"),
):
    """Run an interactive 1-command demonstration showing failure detection, feedback, and repair."""
    console.print(Panel.fit(
        "[bold cyan]ADAPTIVE CODING AGENT HARNESS DEMONSTRATION[/bold cyan]\n"
        "[italic]Proving that automated test failure feedback enables agents to self-correct[/italic]",
        border_style="cyan",
    ))

    runner = BenchmarkRunner()
    tasks = runner.load_tasks(task_id="task_bug_02")
    if not tasks:
        console.print("[bold red]Demo task 'task_bug_02' not found.[/bold red]")
        raise typer.Exit(1)
    task = tasks[0]

    cfg = HarnessConfig.from_yaml("configs/developer.yaml")
    cfg.name = "demo-run"
    cfg.dry_run = dry_run

    backend = get_backend(
        opencode_cmd=get_settings().opencode_command,
        model=cfg.model or get_settings().gemini_model,
        dry_run=cfg.dry_run,
    )

    workspace = runner.prepare_isolated_workspace(task)
    console.print(f"[bold yellow]Task:[/bold yellow] {task.title}")
    console.print(f"[bold yellow]Target Repository:[/bold yellow] {task.repository}")
    console.print(f"[bold yellow]Expected Behavior:[/bold yellow] {task.expected_behavior}\n")

    controller = FeedbackLoopController(
        task=task,
        workspace=workspace,
        config=cfg,
        backend=backend,
    )

    record = controller.execute()
    db = RunDatabase(get_settings().db_path)
    db.save_run(record)

    console.print("\n" + "=" * 60)
    console.print(Panel.fit(
        f"[bold green]DEMO COMPLETED SUCCESSFULLY[/bold green]\n"
        f"Final Status: [bold green]{record.status.value}[/bold green]\n"
        f"Iterations Taken: [cyan]{record.iteration_count}[/cyan]\n"
        f"Execution Time: [cyan]{record.duration_seconds}s[/cyan]\n"
        f"Agent Time: [cyan]{record.timing.agent_time_seconds}s[/cyan] | Test Time: [cyan]{record.timing.test_time_seconds}s[/cyan]\n"
        f"Files Modified: [cyan]{record.git_diff_summary}[/cyan]",
        border_style="green",
    ))


@app.command("dashboard")
def start_dashboard(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address"),
    port: int = typer.Option(8000, "--port", "-p", help="Port number"),
):
    """Launch the FastAPI evaluation dashboard."""
    import uvicorn
    from harness.server import app as server_app

    console.print(f"[bold green]Starting Harness Dashboard at http://{host}:{port}[/bold green]")
    uvicorn.run(server_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    app()
