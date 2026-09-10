"""Real OpenCode client executing headless runs against Gemini."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from harness.logging_config import logger
from harness.models import AgentMode, ToolPermissionsConfig
from harness.opencode.base import AgentBackend, AgentResponse
from harness.opencode.parser import OpenCodeOutputParser


class OpenCodeBackend(AgentBackend):
    """Executes real OpenCode CLI runs against Gemini models."""

    def __init__(
        self,
        opencode_cmd: str = "opencode",
        model: str = "google/gemini-2.5-flash",
    ):
        self.opencode_cmd = opencode_cmd
        self.model = model

    def is_available(self) -> bool:
        """Verify that OpenCode binary exists and Gemini API key is configured."""
        has_binary = shutil.which(self.opencode_cmd) is not None
        has_key = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
        return has_binary and has_key

    def check_preconditions(self) -> Optional[str]:
        """Check prerequisites and return an error message if missing."""
        if not shutil.which(self.opencode_cmd):
            return (
                f"OpenCode executable '{self.opencode_cmd}' not found in PATH. "
                "Ensure OpenCode is installed or specify OPENCODE_COMMAND in .env."
            )
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            return (
                "GEMINI_API_KEY is not configured in the environment or .env file. "
                "Provide a valid key or run with '--dry-run' to use the simulated backend."
            )
        return None

    def execute_turn(
        self,
        prompt: str,
        workspace: Path,
        mode: AgentMode = AgentMode.DEVELOPER,
        permissions: Optional[ToolPermissionsConfig] = None,
        timeout: int = 120,
        session_id: Optional[str] = None,
    ) -> AgentResponse:
        """Execute a single agent turn using `opencode run`."""
        error_precondition = self.check_preconditions()
        if error_precondition:
            logger.error(error_precondition)
            return AgentResponse(
                text="",
                exit_code=1,
                error_message=error_precondition,
            )

        cmd = [
            self.opencode_cmd,
            "run",
            prompt,
            "--dir",
            str(workspace.resolve()),
            "--format",
            "json",
            "-m",
            self.model,
            "--auto",
        ]

        if session_id:
            cmd.extend(["--session", session_id])

        logger.info(f"Invoking OpenCode (model: {self.model}) in {workspace.name}")
        env = os.environ.copy()

        try:
            process = subprocess.run(
                cmd,
                cwd=str(workspace.resolve()),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            stdout = process.stdout or ""
            stderr = process.stderr or ""
            exit_code = process.returncode

            response = OpenCodeOutputParser.parse_stream(stdout)
            response.exit_code = exit_code

            if exit_code != 0 and not response.error_message:
                response.error_message = stderr.strip() or f"OpenCode exited with code {exit_code}"

            # If session was recorded, try to enrich token metrics via export
            if response.session_id and (not response.token_usage.is_available or response.token_usage.total_tokens is None):
                self._enrich_via_export(response.session_id, response, workspace)

            return response

        except subprocess.TimeoutExpired:
            logger.error(f"OpenCode run timed out after {timeout} seconds")
            return AgentResponse(
                text="",
                exit_code=124,
                error_message=f"Execution timed out after {timeout} seconds",
            )
        except Exception as e:
            logger.error(f"Failed to execute OpenCode: {e}")
            return AgentResponse(
                text="",
                exit_code=1,
                error_message=str(e),
            )

    def _enrich_via_export(self, session_id: str, response: AgentResponse, workspace: Path) -> None:
        """Query `opencode export <session_id>` to retrieve exact token counts."""
        try:
            proc = subprocess.run(
                [self.opencode_cmd, "export", session_id],
                cwd=str(workspace.resolve()),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if proc.returncode == 0 and proc.stdout:
                tokens, files, tools = OpenCodeOutputParser.parse_export_session(proc.stdout)
                if tokens.is_available and tokens.total_tokens is not None:
                    response.token_usage = tokens
                if tools:
                    for k, v in tools.items():
                        response.tool_calls[k] = response.tool_calls.get(k, 0) + v
        except Exception:
            pass  # Fallback to stream tokens if export fails
