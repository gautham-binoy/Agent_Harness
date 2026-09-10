"""Unit tests for feedback parsing, error classification, and database storage."""

from harness.feedback.analyzer import FeedbackAnalyzer
from harness.models import FailureCategory, RunRecord, Task, TokenUsage
from harness.storage.database import RunDatabase


def test_parse_pytest_pass():
    output = "===== 42 passed in 0.12s ====="
    res = FeedbackAnalyzer.parse_test_output(output, "pytest -q", exit_code=0)
    assert res.passed is True
    assert res.passed_count == 42
    assert res.failed_count == 0


def test_parse_pytest_fail():
    output = (
        "_____________________________ test_login_success _____________________________\n"
        "def test_login_success():\n"
        ">       login('alice')\n"
        "E       TypeError: login() missing required argument 'password'\n"
        "app/test_main.py:10: TypeError\n"
        "_____________________________ test_invalid_token _____________________________\n"
        "def test_invalid_token():\n"
        ">       assert response.status_code == 401\n"
        "E       AssertionError: expected 401, got 500\n"
        "app/test_main.py:18: AssertionError\n"
        "=========================== 40 passed, 2 failed in 0.35s ==========================="
    )
    res = FeedbackAnalyzer.parse_test_output(output, "pytest -q", exit_code=1)
    assert res.passed is False
    assert res.passed_count == 40
    assert res.failed_count == 2
    assert len(res.failures) == 2
    assert res.failures[0].test_name == "test_login_success"
    assert "TypeError: login() missing required argument 'password'" in res.failures[0].message
    assert res.failures[1].test_name == "test_invalid_token"
    assert "AssertionError: expected 401, got 500" in res.failures[1].message

    # Test remediation prompt formatting
    prompt = FeedbackAnalyzer.format_remediation_prompt(res)
    assert "TEST EXECUTION RESULT" in prompt
    assert "Status:\nFAILED" in prompt
    assert "1. test_login_success" in prompt
    assert "2. test_invalid_token" in prompt


def test_classify_failure():
    # Syntax Error
    syntax_raw = "SyntaxError: invalid syntax at line 12"
    res_syntax = FeedbackAnalyzer.parse_test_output(syntax_raw, "pytest", exit_code=1)
    cat = FeedbackAnalyzer.classify_failure(res_syntax)
    assert cat == FailureCategory.SYNTAX_ERROR

    # Dependency Error
    dep_raw = "ModuleNotFoundError: No module named 'jwt'"
    res_dep = FeedbackAnalyzer.parse_test_output(dep_raw, "pytest", exit_code=1)
    cat = FeedbackAnalyzer.classify_failure(res_dep)
    assert cat == FailureCategory.DEPENDENCY_ERROR

    # Test Failure
    test_raw = "AssertionError: expected 200 got 404"
    res_test = FeedbackAnalyzer.parse_test_output(test_raw, "pytest", exit_code=1)
    cat = FeedbackAnalyzer.classify_failure(res_test)
    assert cat == FailureCategory.TEST_FAILURE


def test_database_persistence(tmp_path):
    db_file = tmp_path / "test_runs.db"
    db = RunDatabase(db_file)

    run = RunRecord(
        run_id="run_test_001",
        task_id="task_jwt",
        task_title="Add JWT authentication",
        repository="fastapi_app",
        agent_mode="developer",
        model="google/gemini-2.5-flash",
        config_name="developer",
        start_time="2026-09-10T12:00:00",
        duration_seconds=15.2,
        iteration_count=2,
        success=True,
        test_passed=True,
        token_usage=TokenUsage(input_tokens=1500, output_tokens=300, total_tokens=1800, cost=0.0005),
    )

    db.save_run(run)
    fetched = db.get_run("run_test_001")
    assert fetched is not None
    assert fetched.run_id == "run_test_001"
    assert fetched.success is True
    assert fetched.token_usage.total_tokens == 1800

    stats = db.get_stats("developer")
    assert stats["total_runs"] == 1
    assert stats["successful_runs"] == 1
    assert stats["success_rate"] == 100.0
