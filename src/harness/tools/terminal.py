"""Protected terminal command execution engine."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple
from harness.logging_config import logger
from harness.tools.permissions import PermissionManager, SecurityException


class SafeTerminal:
    """Executes permitted subprocess commands inside the workspace."""

    def __init__(self, workspace: Path, permissions: Optional[PermissionManager] = None):
        self.workspace = workspace.resolve()
        self.permissions = permissions or PermissionManager()

    def run_command(
        self,
        command: str,
        timeout: int = 120,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str, str]:
        """Execute command returning (exit_code, stdout, stderr)."""
        ok, err = self.permissions.validate_command(command)
        if not ok:
            logger.warning(f"Blocked dangerous command: {command} ({err})")
            raise SecurityException(err)

        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)

        logger.info(f"Running terminal command: {command}")
        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            return res.returncode, res.stdout or "", res.stderr or ""
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after {timeout} seconds: {command}")
            return 124, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            logger.error(f"Command failed to execute: {e}")
            return 1, "", str(e)
