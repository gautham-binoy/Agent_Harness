"""Integration test for BenchmarkRunner and task execution."""

from pathlib import Path
from harness.config import HarnessConfig
from harness.evaluation.benchmark import BenchmarkRunner
from harness.evaluation.metrics import MetricsCalculator
from harness.models import AgentMode
from harness.opencode.mock import MockBackend
from harness.storage.database import RunDatabase


def test_load_tasks():
    runner = BenchmarkRunner()
    tasks = runner.load_tasks()
    assert len(tasks) == 30

    bug_tasks = runner.load_tasks(category="bug_fix")
    assert len(bug_tasks) == 10

    single_task = runner.load_tasks(task_id="task_bug_01")
    assert len(single_task) == 1
    assert single_task[0].id == "task_bug_01"


def test_run_benchmark_task_with_mock_backend(tmp_path):
    db = RunDatabase(tmp_path / "bench_test.db")
    runner = BenchmarkRunner(db=db)

    config = HarnessConfig(
        name="test-harness",
        max_iterations=3,
        feedback={"tests": True, "linter": False},
    )
    backend = MockBackend()

    tasks = runner.load_tasks(task_id="task_bug_01")
    assert len(tasks) == 1
    task = tasks[0]

    record = runner.run_task(task, config, backend)
    assert record.task_id == "task_bug_01"
    assert record.success is True
    assert record.iteration_count >= 1

    stored = db.get_run(record.run_id)
    assert stored is not None
    assert stored.success is True
