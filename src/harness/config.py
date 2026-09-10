"""Configuration management for the adaptive harness."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from harness.models import AgentMode, ToolPermissionsConfig


class EnvSettings(BaseSettings):
    """Settings loaded from environment variables and .env file."""

    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="google/gemini-2.5-flash", alias="GEMINI_MODEL")
    opencode_command: str = Field(default="opencode", alias="OPENCODE_COMMAND")
    max_iterations: int = Field(default=5, alias="MAX_ITERATIONS")
    command_timeout: int = Field(default=120, alias="COMMAND_TIMEOUT")
    test_timeout: int = Field(default=120, alias="TEST_TIMEOUT")
    workspace_root: str = Field(default="./workspace", alias="WORKSPACE_ROOT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    db_path: str = Field(default="./runs.db", alias="DB_PATH")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class ContextConfig(BaseModel):
    repository_summary: bool = True
    git_status: bool = True
    directory_tree: bool = True
    max_tree_depth: int = 3
    file_overview_limit: int = 15


class FeedbackConfig(BaseModel):
    tests: bool = True
    linter: bool = True
    max_remediation_chars: int = 3000


class AgentConfig(BaseModel):
    mode: AgentMode = AgentMode.DEVELOPER
    temperature: float = 0.2
    custom_prompt: Optional[str] = None


class HarnessConfig(BaseModel):
    """Complete scaffolding configuration for a harness run."""

    name: str = "full-harness"
    agent: AgentConfig = Field(default_factory=AgentConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    tools: ToolPermissionsConfig = Field(default_factory=ToolPermissionsConfig)
    feedback: FeedbackConfig = Field(default_factory=FeedbackConfig)
    max_iterations: int = 5
    model: Optional[str] = None
    dry_run: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> HarnessConfig:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)

    def to_yaml(self, path: str | Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.model_dump(mode="json"), f, default_flow_style=False)


def get_settings() -> EnvSettings:
    """Get the global environment settings singleton."""
    return EnvSettings()
