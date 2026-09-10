"""Analyzes test and linter failures, classifies errors, and formats remediation prompts."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple
from harness.models import (
    FailureCategory,
    LintResult,
    TestFailureItem,
    TestResult,
)


class FeedbackAnalyzer:
    """Analyzes raw test output and linter results into structured remediation prompts."""

    @classmethod
    def parse_test_output(cls, raw: str, command: str, exit_code: int) -> TestResult:
        """Parse raw pytest/unittest/npm output to extract counts and failure details."""
        passed = exit_code == 0
        failures: List[TestFailureItem] = []
        passed_count = 0
        failed_count = 0
        total = 0

        # Extract pytest summary lines, e.g., "42 passed, 3 failed in 0.23s" or "3 failed in 0.1s"
        summary_match = re.search(r"(=+\s*)?((?:(\d+)\s+passed)?[,\s]*(?:(\d+)\s+failed)?[,\s]*(?:(\d+)\s+error)?[^=\n]*)(?:=*)", raw)
        summary_text = ""

        # Check for pytest counts
        pass_m = re.search(r"(\d+)\s+passed", raw)
        fail_m = re.search(r"(\d+)\s+failed", raw)
        err_m = re.search(r"(\d+)\s+error", raw)

        if pass_m:
            passed_count = int(pass_m.group(1))
        if fail_m:
            failed_count += int(fail_m.group(1))
        if err_m:
            failed_count += int(err_m.group(1))

        total = passed_count + failed_count
        if total == 0 and passed:
            summary_text = "All tests passed"
        elif total == 0 and not passed:
            summary_text = f"Tests failed with exit code {exit_code}"
        else:
            summary_text = f"{passed_count} passed, {failed_count} failed"

        # Parse detailed failures from pytest
        # Sections usually start with "___ test_name ___" or "FAILED tests/test_file.py::test_name"
        failure_blocks = re.findall(
            r"(?:_{3,}\s*([\w.-]+)\s*_{3,}|FAILED\s+([^\s:]+::([^\s]+)))\n(.*?)(?=\n_{3,}|\nFAILED|\n=+\s*(?:FAILURES|short test summary|\d+\s+passed|\d+\s+failed)|\Z)",
            raw,
            re.DOTALL,
        )

        for block in failure_blocks:
            test_name = block[0] or block[2] or block[1] or "test_unknown"
            body = block[3].strip()

            # Find the exception line (last non-empty line or line starting with E )
            error_msg = ""
            e_lines = [l[2:].strip() for l in body.splitlines() if l.startswith("E   ")]
            if e_lines:
                error_msg = "\n".join(e_lines[-3:])
            else:
                last_lines = [l.strip() for l in body.splitlines() if l.strip()]
                error_msg = last_lines[-1] if last_lines else "Assertion failed"

            failures.append(
                TestFailureItem(
                    test_name=test_name,
                    message=error_msg,
                    details=body[:800],
                )
            )

        # If no regex blocks matched but exit code != 0, extract non-zero error lines
        if not passed and not failures:
            error_lines = [l.strip() for l in raw.splitlines() if any(k in l for k in ("Error", "FAILED", "Exception", "Traceback"))]
            msg = "\n".join(error_lines[:5]) if error_lines else raw[-400:]
            failures.append(
                TestFailureItem(
                    test_name="general_execution_failure",
                    message=msg or "Test execution failed without standard pytest summary",
                    details=raw[:1000],
                )
            )
            failed_count = max(1, failed_count)

        return TestResult(
            passed=passed and failed_count == 0,
            command=command,
            exit_code=exit_code,
            summary=summary_text,
            total=total,
            passed_count=passed_count,
            failed_count=failed_count,
            failures=failures,
            raw_output=raw,
        )

    @classmethod
    def classify_failure(
        cls,
        test_result: Optional[TestResult],
        lint_result: Optional[LintResult] = None,
        timeout: bool = False,
    ) -> FailureCategory:
        """Categorize failure into standardized taxonomy."""
        if timeout:
            return FailureCategory.TIMEOUT

        text = ""
        if test_result:
            text += test_result.raw_output + " " + " ".join(f.message for f in test_result.failures)
        if lint_result:
            text += lint_result.raw_output

        text_lower = text.lower()

        # Syntax or compile
        if any(s in text_lower for s in ("syntaxerror", "indentationerror", "syntax error", "unexpected token")):
            return FailureCategory.SYNTAX_ERROR

        # Dependency
        if any(s in text_lower for s in ("modulenotfounderror", "importerror", "no module named", "cannot find module")):
            return FailureCategory.DEPENDENCY_ERROR

        # Permission
        if any(s in text_lower for s in ("permissionerror", "permission denied", "securityexception")):
            return FailureCategory.PERMISSION_FAILURE

        # Timeout
        if any(s in text_lower for s in ("timed out", "timeout expired", "timedout")):
            return FailureCategory.TIMEOUT

        # Test failure (Assertion / Type / Attribute)
        if any(s in text_lower for s in ("assertionerror", "typeerror", "valueerror", "attributeerror", "failed")):
            return FailureCategory.TEST_FAILURE

        if lint_result and not lint_result.passed:
            return FailureCategory.WRONG_IMPLEMENTATION

        return FailureCategory.WRONG_IMPLEMENTATION

    @classmethod
    def format_remediation_prompt(
        cls,
        test_result: TestResult,
        lint_result: Optional[LintResult] = None,
    ) -> str:
        """Generate structured failure feedback prompt as specified in section 10."""
        lines = [
            "TEST EXECUTION RESULT",
            "",
            "Command:",
            test_result.command,
            "",
            "Status:",
            "PASSED" if test_result.passed else "FAILED",
            "",
            "Summary:",
            f"{test_result.passed_count} passed",
            f"{test_result.failed_count} failed",
            "",
        ]

        if test_result.failures:
            lines.append("Failures:")
            lines.append("")
            for i, fail in enumerate(test_result.failures, 1):
                lines.append(f"{i}. {fail.test_name}")
                lines.append(f"   {fail.message}")
                lines.append("")

        # Append Linter results if available and failing
        if lint_result and not lint_result.passed and lint_result.issues:
            lines.extend([
                "LINTER RESULT",
                "",
                "Status: FAILED",
                f"Errors: {lint_result.errors_count}",
                "",
                "Top issues:",
            ])
            for issue in lint_result.issues[:5]:
                pos = f":{issue.line}" if issue.line else ""
                lines.append(f"- {issue.file}{pos}: {issue.code or ''} {issue.message}")
            lines.append("")

        lines.extend([
            "Fix the implementation based on these failures.",
            "Do not modify tests merely to make them pass.",
            "After making changes, verify your implementation fulfills the required behavior.",
        ])

        return "\n".join(lines)
