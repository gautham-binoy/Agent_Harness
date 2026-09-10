"""Base classes for agent backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from harness.models import AgentMode, TokenUsage, ToolPermissionsConfig


class AgentResponse(BaseModel):
    """Response returned from a single agent turn."""

    text: str = ""
    tool_calls: Dict[str, int] = Field(default_factory=dict)
    files_modified: List[str] = Field(default_factory=list)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    session_id: Optional[str] = None
    exit_code: int = 0
    error_message: Optional[str] = None
    raw_events: List[Dict[str, Any]] = Field(default_factory=list)


class AgentBackend(ABC):
    """Abstract interface for invoking the coding agent."""

    @abstractmethod
    def execute_turn(
        self,
        prompt: str,
        workspace: Path,
        mode: AgentMode = AgentMode.DEVELOPER,
        permissions: Optional[ToolPermissionsConfig] = None,
        timeout: int = 120,
        session_id: Optional[str] = None,
    ) -> AgentResponse:
        """Execute a single agent turn within the specified workspace."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether the backend dependencies/credentials are satisfied."""
        pass
