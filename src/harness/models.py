"""Core data models and type definitions for the adaptive harness."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentMode(str, Enum):
    DEVELOPER = "developer"
    TEST_WRITER = "test_writer"
    MIGRATION = "migration"


class EvaluationStatus(str, Enum):
    SUCCESS = "SUCCESS"    # All required and validation tests pass, no critical errors
    PARTIAL = "PARTIAL"    # Public tests pass but hidden/regression tests fail
    FAILURE = "FAILURE"    # Required validation tests fail, timeout, or execution crash


class FailureCategory(str, Enum):
    SYNTAX_ERROR = "syntax_error"
    COMPILE_ERROR = "compile_error"
    TEST_FAILURE = "test_failure"
    LINT_FAILURE = "lint_failure"
    DEPENDENCY_ERROR = "dependency_error"
    WRONG_IMPLEMENTATION = "wrong_implementation"
    CONTEXT_FAILURE = "context_failure"
    TOOL_FAILURE = "tool_failure"
    TIMEOUT = "timeout"
    PERMISSION_FAILURE = "permission_failure"
    ENVIRONMENT_ERROR = "environment_error"
    UNKNOWN = "unknown"


class FileSystemPermissions(BaseModel):
    read: bool = True
    write: bool = True


class TerminalPermissions(BaseModel):
    enabled: bool = True
    allowed_commands: Optional[List[str]] = None
    blocked_commands: List[str] = Field(
        default_factory=lambda: [
            "rm -rf /",
            "rm -rf ~",
            "mkfs",
            "dd if=",
            ":(){ :|:& };:",
            "chmod -R 777 /",
            "git clean -fdx /",
            "sudo",
            "shutdown",
            "reboot",
            "poweroff",
        ]
    )


class GitPermissions(BaseModel):
    read: bool = True
    write: bool = False
    allow_commit: bool = False
    allow_push: bool = False


class TestPermissions(BaseModel):
    enabled: bool = True


class LinterPermissions(BaseModel):
    enabled: bool = True


class ToolPermissionsConfig(BaseModel):
    filesystem: FileSystemPermissions = Field(default_factory=FileSystemPermissions)
    terminal: TerminalPermissions = Field(default_factory=TerminalPermissions)
    git: GitPermissions = Field(default_factory=GitPermissions)
    tests: TestPermissions = Field(default_factory=TestPermissions)
    linter: LinterPermissions = Field(default_factory=LinterPermissions)


class Task(BaseModel):
    id: str
    title: str
    category: str = "feature"  # bug_fix, feature, testing, migration
    difficulty: str = "medium"  # easy, medium, hard
    repository: str
    description: str
    expected_behavior: str
    test_command: str = "pytest -q"
    hidden_test_command: Optional[str] = None
    lint_command: Optional[str] = None
    timeout: int = 120
    expected_changed_files: List[str] = Field(default_factory=list)
    setup_action: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TestFailureItem(BaseModel):
    test_name: str
    message: str
    details: Optional[str] = None


class TestResult(BaseModel):
    passed: bool
    command: str
    exit_code: int = 0
    summary: str = ""
    total: int = 0
    passed_count: int = 0
    failed_count: int = 0
    failures: List[TestFailureItem] = Field(default_factory=list)
    raw_output: str = ""


class LintIssueItem(BaseModel):
    file: str
    line: Optional[int] = None
    column: Optional[int] = None
    code: Optional[str] = None
    message: str = ""


class LintResult(BaseModel):
    passed: bool
    command: str
    exit_code: int = 0
    errors_count: int = 0
    warnings_count: int = 0
    issues: List[LintIssueItem] = Field(default_factory=list)
    raw_output: str = ""


class TokenUsage(BaseModel):
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost: Optional[float] = 0.0
    is_available: bool = True

    @classmethod
    def unavailable(cls) -> TokenUsage:
        return cls(is_available=False)


class TimingBreakdown(BaseModel):
    total_time_seconds: float = 0.0
    agent_time_seconds: float = 0.0
    test_time_seconds: float = 0.0
    feedback_time_seconds: float = 0.0


class IterationRecord(BaseModel):
    iteration: int
    prompt: str
    response_summary: str = ""
    files_changed: List[str] = Field(default_factory=list)
    test_result: Optional[TestResult] = None
    lint_result: Optional[LintResult] = None
    tool_calls: Dict[str, int] = Field(default_factory=dict)
    duration_seconds: float = 0.0
    timing: TimingBreakdown = Field(default_factory=TimingBreakdown)


class RunRecord(BaseModel):
    run_id: str
    task_id: str
    task_title: str
    repository: str
    agent_mode: str
    model: str
    config_name: str = "default"
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: float = 0.0
    iteration_count: int = 0
    success: bool = False
    status: EvaluationStatus = EvaluationStatus.FAILURE
    test_passed: bool = False
    hidden_test_passed: Optional[bool] = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    tool_calls: Dict[str, int] = Field(default_factory=dict)
    timing: TimingBreakdown = Field(default_factory=TimingBreakdown)
    failure_category: Optional[FailureCategory] = None
    failure_reason: Optional[str] = None
    git_diff_summary: Optional[str] = None
    history: List[IterationRecord] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
