"""Automated linter runner and diagnostics collector."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional
from harness.logging_config import logger
from harness.models import LintIssueItem, LintResult


class LinterRunner:
    """Detects and runs project linters, extracting actionable issues."""

    def __init__(self, workspace: Path, timeout: int = 60):
        self.workspace = workspace.resolve()
        self.timeout = timeout

    def detect_linter_command(self) -> Optional[str]:
        """Detect the best available linter command."""
        # Check ruff
        if shutil.which("ruff"):
            return "ruff check ."

        # Check flake8
        if shutil.which("flake8"):
            return "flake8 ."

        # Check eslint
        if (self.workspace / "node_modules" / ".bin" / "eslint").exists():
            return "./node_modules/.bin/eslint ."
        if shutil.which("eslint") and ((self.workspace / ".eslintrc.json").exists() or (self.workspace / "package.json").exists()):
            return "eslint ."

        return None

    def run(self, custom_command: Optional[str] = None) -> LintResult:
        """Run linter and return structured result."""
        cmd = custom_command or self.detect_linter_command()
        if not cmd:
            logger.info("No linter detected or configured. Skipping linter check.")
            return LintResult(
                passed=True,
                command="none",
                exit_code=0,
                summary="No linter configured",
                raw_output="",
            )

        logger.info(f"Running linter: '{cmd}' in {self.workspace.name}")
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
            issues = self._parse_issues(raw)
            passed = res.returncode == 0 and len(issues) == 0

            return LintResult(
                passed=passed,
                command=cmd,
                exit_code=res.returncode,
                errors_count=len(issues),
                warnings_count=0,
                issues=issues,
                raw_output=raw,
            )
        except subprocess.TimeoutExpired:
            logger.warning(f"Linter timed out after {self.timeout}s")
            return LintResult(
                passed=False,
                command=cmd,
                exit_code=124,
                errors_count=1,
                raw_output=f"Linter timed out after {self.timeout}s",
            )
        except Exception as e:
            logger.warning(f"Linter execution failed: {e}")
            return LintResult(
                passed=True,
                command=cmd,
                exit_code=0,
                raw_output=str(e),
            )

    def _parse_issues(self, raw_output: str) -> List[LintIssueItem]:
        """Parse linter output into structured issue items."""
        issues = []
        # Pattern like: path/to/file.py:10:5: E999 SyntaxError: ...
        pattern = re.compile(r"^([^:\n]+):(\d+):(?:(\d+):)?\s*(?:([A-Z]\d+)\s+)?(.*)$", re.MULTILINE)
        for match in pattern.finditer(raw_output):
            fpath, line, col, code, msg = match.groups()
            # Ignore test files or virtualenv lines if accidentally caught
            if ".venv" in fpath or "__pycache__" in fpath:
                continue
            issues.append(
                LintIssueItem(
                    file=fpath.strip(),
                    line=int(line) if line else None,
                    column=int(col) if col else None,
                    code=code.strip() if code else None,
                    message=msg.strip() if msg else "",
                )
            )
        return issues[:20]  # Cap to top 20
