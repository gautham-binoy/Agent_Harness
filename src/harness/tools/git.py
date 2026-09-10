"""Safe Git state tracking and difference extraction."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional, Tuple
from harness.logging_config import logger


class GitTracker:
    """Safely records Git states before and after agent tasks without pushing."""

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()

    def is_git_repo(self) -> bool:
        return (self.workspace / ".git").exists()

    def get_commit_hash(self) -> Optional[str]:
        """Get current HEAD commit hash."""
        if not self.is_git_repo():
            return None
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception as e:
            logger.debug(f"Git rev-parse failed: {e}")
        return None

    def get_status(self) -> str:
        """Get short git status."""
        if not self.is_git_repo():
            return "not a git repo"
        try:
            res = subprocess.run(
                ["git", "status", "--short"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception as e:
            logger.debug(f"Git status failed: {e}")
        return "unknown"

    def get_diff(self) -> str:
        """Get git diff of working tree."""
        if not self.is_git_repo():
            return ""
        try:
            res = subprocess.run(
                ["git", "diff"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                return res.stdout
        except Exception as e:
            logger.debug(f"Git diff failed: {e}")
        return ""

    def get_diff_stat(self) -> str:
        """Get git diff --stat summary."""
        if not self.is_git_repo():
            return ""
        try:
            res = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception as e:
            logger.debug(f"Git diff --stat failed: {e}")
        return ""

    def get_changed_files(self) -> List[str]:
        """Get list of modified or added files."""
        if not self.is_git_repo():
            return []
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                files = []
                for line in res.stdout.splitlines():
                    if len(line) >= 3:
                        files.append(line[3:].strip())
                return files
        except Exception as e:
            logger.debug(f"Git status --porcelain failed: {e}")
        return []
