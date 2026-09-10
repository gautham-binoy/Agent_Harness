"""Migration Agent Mode implementation."""

from __future__ import annotations

from typing import Dict
from harness.agents.base import BaseAgentMode
from harness.models import AgentMode


class MigrationMode(BaseAgentMode):
    """Specialized mode for dependency upgrades, framework migrations, and deprecation fixes."""

    mode = AgentMode.MIGRATION

    def get_system_instructions(self) -> str:
        return (
            "You are a Migration & Modernization Specialist operating in Migration Mode.\n"
            "Your workflow is:\n"
            "1. Inspect dependency manifests (e.g. pyproject.toml, requirements.txt, package.json).\n"
            "2. Identify target version changes and known breaking changes or deprecations.\n"
            "3. Update manifests and adapt call sites, imports, and configuration.\n"
            "4. Execute test suite to isolate migration regressions.\n"
            "5. Iterate on failures until all tests pass with the upgraded dependencies.\n"
            "6. Conclude with a concise migration changelog of upgraded packages and altered APIs."
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
