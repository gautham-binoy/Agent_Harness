"""Unit tests for configuration and data models."""

from harness.config import HarnessConfig, get_settings
from harness.models import AgentMode, FailureCategory, RunRecord, Task, TokenUsage


def test_default_settings():
    settings = get_settings()
    assert settings.opencode_command == "opencode"
    assert settings.max_iterations == 5
    assert settings.command_timeout == 120


def test_harness_config_defaults():
    config = HarnessConfig()
    assert config.name == "full-harness"
    assert config.agent.mode == AgentMode.DEVELOPER
    assert config.context.repository_summary is True
    assert config.feedback.tests is True
    assert config.feedback.linter is True
    assert config.tools.filesystem.write is True
    assert config.tools.git.write is False


def test_harness_config_yaml_roundtrip(tmp_path):
    config = HarnessConfig(name="test-config", max_iterations=3)
    yaml_file = tmp_path / "config.yaml"
    config.to_yaml(yaml_file)

    loaded = HarnessConfig.from_yaml(yaml_file)
    assert loaded.name == "test-config"
    assert loaded.max_iterations == 3


def test_task_model():
    task = Task(
        id="task_01",
        title="Add validation",
        category="bug_fix",
        repository="example",
        description="Fix empty string bug",
        expected_behavior="Return 400 on empty string",
        test_command="pytest -q",
    )
    assert task.id == "task_01"
    assert task.category == "bug_fix"


def test_run_record_metrics():
    record = RunRecord(
        run_id="run_20260910_001",
        task_id="task_01",
        task_title="Add validation",
        repository="example",
        agent_mode="developer",
        model="google/gemini-2.5-flash",
        start_time="2026-09-10T12:00:00",
        duration_seconds=12.5,
        iteration_count=2,
        success=True,
        test_passed=True,
        token_usage=TokenUsage(input_tokens=1000, output_tokens=150, total_tokens=1150),
    )
    assert record.success is True
    assert record.token_usage.total_tokens == 1150
