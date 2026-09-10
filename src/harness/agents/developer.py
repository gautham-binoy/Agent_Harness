"""Developer Agent Mode implementation."""

from __future__ import annotations

from typing import Dict
from harness.agents.base import BaseAgentMode
from harness.models import AgentMode


class DeveloperMode(BaseAgentMode):
    """General software engineering mode focused on end-to-end task completion."""

    mode = AgentMode.DEVELOPER

    def get_system_instructions(self) -> str:
        return (
            "You are an expert Software Engineer operating in Developer Mode.\n"
            "Your workflow is:\n"
            "1. Understand repository structure and existing patterns.\n"
            "2. Inspect relevant files and entrypoints before making changes.\n"
            "3. Plan minimal, clean, and robust modifications.\n"
            "4. Modify code to implement the requested feature or fix the bug.\n"
            "5. Verify your solution against existing tests and linters.\n"
            "6. Refine implementation if tests or linters fail.\n"
            "7. Ensure no regressions or unrelated file changes are introduced."
        )

    def get_recommended_tools(self) -> Dict[str, bool]:
        return {
            "filesystem_read": True,
            "filesystem_write": True,
            "terminal": True,
            "git_read": True,
            "git_write": False,
            "tests": True,
            "linter": True,
        }
