"""Executes verification suites and collects test and linter outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple
from harness.feedback.analyzer import FeedbackAnalyzer
from harness.models import LintResult, TestResult
from harness.tools.linter import LinterRunner
from harness.tools.tests import TestRunner


class FeedbackCollector:
    """Collects verification feedback from tests and linters post-turn."""

    def __init__(self, workspace: Path, test_timeout: int = 120):
        self.workspace = workspace.resolve()
        self.test_runner = TestRunner(self.workspace, timeout=test_timeout)
        self.linter_runner = LinterRunner(self.workspace)

    def collect(
        self,
        test_command: str = "pytest -q",
        run_linter: bool = True,
        custom_lint_command: Optional[str] = None,
    ) -> Tuple[TestResult, Optional[LintResult]]:
        """Run tests and optional linter, returning parsed results."""
        # 1. Run tests
        raw_test = self.test_runner.run(test_command)
        parsed_test = FeedbackAnalyzer.parse_test_output(
            raw=raw_test.raw_output,
            command=test_command,
            exit_code=raw_test.exit_code,
        )

        # 2. Run linter if requested
        lint_result: Optional[LintResult] = None
        if run_linter:
            lint_result = self.linter_runner.run(custom_lint_command)

        return parsed_test, lint_result
