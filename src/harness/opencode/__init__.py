"""OpenCode adapter and agent backend interfaces."""

from harness.opencode.base import AgentBackend, AgentResponse
from harness.opencode.client import OpenCodeBackend
from harness.opencode.mock import MockBackend

__all__ = ["AgentBackend", "AgentResponse", "OpenCodeBackend", "MockBackend", "get_backend"]


def get_backend(
    opencode_cmd: str = "opencode",
    model: str = "google/gemini-2.5-flash",
    dry_run: bool = False,
) -> AgentBackend:
    """Factory to retrieve appropriate backend based on mode and availability."""
    if dry_run:
        return MockBackend()
    return OpenCodeBackend(opencode_cmd=opencode_cmd, model=model)
