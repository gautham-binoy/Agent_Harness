"""Combines task requirements, repository context, and agent mode prompts."""

from __future__ import annotations

from pathlib import Path
from harness.config import HarnessConfig
from harness.context.repository import RepositoryInspector
from harness.models import AgentMode, Task


class TaskContextBuilder:
    """Builds the initial structured prompt for the agent turn."""

    @staticmethod
    def build_initial_prompt(
        task: Task,
        workspace: Path,
        config: HarnessConfig,
        mode_instruction: str,
    ) -> str:
        """Compose the full task prompt including optional repository context."""
        sections = []

        # 1. Mode Header & System Role
        sections.append(f"# AGENT MODE: {config.agent.mode.value.upper()}\n{mode_instruction}")

        # 2. Task Specification
        sections.append(
            f"## TASK: {task.title}\n"
            f"**Category**: {task.category}\n"
            f"**Difficulty**: {task.difficulty}\n\n"
            f"### Description\n{task.description}\n\n"
            f"### Expected Behavior\n{task.expected_behavior}\n\n"
            f"### Verification Command\n`{task.test_command}`"
        )

        # 3. Repository Context (if enabled)
        if config.context.repository_summary:
            inspector = RepositoryInspector(workspace)
            summary = inspector.generate_summary()
            sections.append(summary)

        # 4. Tool & Security Guidance
        guidance = [
            "### EXECUTION GUIDELINES",
            "1. Inspect relevant files before editing.",
            "2. Modify code precisely to fulfill the requested task.",
            "3. Do not introduce extraneous dependencies or modify unrelated files.",
            f"4. Verify your implementation satisfies the test command: `{task.test_command}`.",
            "5. Destructive operations (such as rm -rf /, formatting disks, git push) are strictly prohibited.",
        ]
        sections.append("\n".join(guidance))

        return "\n\n---\n\n".join(sections)
