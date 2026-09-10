"""Automated test execution runner."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional
from harness.logging_config import logger
from harness.models import TestResult


class TestRunner:
    """Executes tests within the workspace and captures raw output."""

    def __init__(self, workspace: Path, timeout: int = 120):
        self.workspace = workspace.resolve()
        self.timeout = timeout

    def run(self, test_command: str = "pytest -q") -> TestResult:
        """Run the specified test command."""
        logger.info(f"Running test suite: '{test_command}' in {self.workspace.name}")

        # If running pytest and within virtualenv, prefer virtualenv pytest
        cmd = test_command
        venv_pytest = Path(sys.executable).parent / "pytest"
        if test_command.startswith("pytest") and venv_pytest.exists():
            cmd = f"{venv_pytest} {test_command[6:]}".strip()

        try:
            res = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            raw = (res.stdout or "") + ("\n" + res.stderr if res.stderr else "")
            passed = res.returncode == 0

            # Initial lightweight summary (detailed parsing handled in feedback analyzer)
            summary = "Tests passed" if passed else f"Tests failed (exit code {res.returncode})"
            return TestResult(
                passed=passed,
                command=test_command,
                exit_code=res.returncode,
                summary=summary,
                raw_output=raw,
            )

        except subprocess.TimeoutExpired:
            logger.error(f"Test run timed out after {self.timeout}s: {test_command}")
            return TestResult(
                passed=False,
                command=test_command,
                exit_code=124,
                summary=f"Timed out after {self.timeout} seconds",
                raw_output=f"Error: test execution exceeded timeout limit of {self.timeout} seconds.",
            )
        except Exception as e:
            logger.error(f"Failed to execute tests: {e}")
            return TestResult(
                passed=False,
                command=test_command,
                exit_code=1,
                summary=f"Execution error: {e}",
                raw_output=str(e),
            )
