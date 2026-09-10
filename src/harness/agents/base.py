"""Base agent mode abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict
from harness.models import AgentMode


class BaseAgentMode(ABC):
    """Abstract base for specialized agent operating modes."""

    mode: AgentMode

    @abstractmethod
    def get_system_instructions(self) -> str:
        """Return the specialized prompt instructions for this mode."""
        pass

    @abstractmethod
    def get_recommended_tools(self) -> Dict[str, bool]:
        """Return default tool access settings tailored for this mode."""
        pass
