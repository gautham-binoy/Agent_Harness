"""Specialized agent operating modes."""

from harness.agents.base import BaseAgentMode
from harness.agents.developer import DeveloperMode
from harness.agents.test_writer import TestWriterMode
from harness.agents.migration import MigrationMode
from harness.models import AgentMode

__all__ = ["BaseAgentMode", "DeveloperMode", "TestWriterMode", "MigrationMode", "get_agent_mode"]


def get_agent_mode(mode: AgentMode | str) -> BaseAgentMode:
    """Retrieve agent mode instance."""
    mode_str = mode.value if isinstance(mode, AgentMode) else str(mode).lower()
    if mode_str in ("test_writer", "testing", "test"):
        return TestWriterMode()
    if mode_str in ("migration", "migrate"):
        return MigrationMode()
    return DeveloperMode()
