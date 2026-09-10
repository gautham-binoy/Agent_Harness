"""Test Writer Agent Mode implementation."""

from __future__ import annotations

from typing import Dict
from harness.agents.base import BaseAgentMode
from harness.models import AgentMode


class TestWriterMode(BaseAgentMode):
    """Specialized mode for adding test suites and expanding test coverage."""

    mode = AgentMode.TEST_WRITER

    def get_system_instructions(self) -> str:
        return (
            "You are a QA and Testing Specialist operating in Test Writer Mode.\n"
            "Your workflow is:\n"
            "1. Inspect production implementation to identify public APIs, edge cases, and failure paths.\n"
            "2. Inspect existing test conventions, fixtures, and assertions in the repository.\n"
            "3. Write idiomatic, deterministic, and isolated unit/integration tests.\n"
            "4. Cover normal behavior, boundary conditions, invalid inputs, and error handling.\n"
            "5. Execute test runner to verify new tests pass and assert real behavior.\n"
            "6. Never write trivial or tautological assertions that always pass."
        )

    def get_recommended_tools(self) -> Dict[str, bool]:
        return {
            "filesystem_read": True,
            "filesystem_write": True,
            "terminal": True,
            "git_read": True,
            "git_write": False,
            "tests": True,
            "linter": False,
        }
