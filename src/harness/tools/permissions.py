"""Tool permission validation and security policies."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from harness.models import ToolPermissionsConfig


class SecurityException(Exception):
    """Raised when an operation violates security or sandbox permissions."""
    pass


class PermissionManager:
    """Enforces fine-grained tool permissions and blocks destructive actions."""

    # Prohibited patterns across shell commands
    DANGEROUS_COMMAND_PATTERNS = [
        r"\brm\s+(-[rfRF]{1,4}\s+)?(/|~|\$HOME|\.\./\.\.)",
        r"\bmkfs\b",
        r"\bfdisk\b",
        r"\bdd\s+if=",
        r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;",  # Fork bomb
        r"\bchmod\s+(-R\s+)?777\s+/",
        r"\bgit\s+push\b",
        r"\bgit\s+clean\s+-fdx\s+/",
        r"\bcurl\b.*\|\s*(ba)?sh",
        r"\bwget\b.*\|\s*(ba)?sh",
        r">+\s*/dev/sd[a-z]",
    ]

    # Sensitive paths that should not be read or leaked
    SENSITIVE_PATH_PATTERNS = [
        r"/etc/shadow",
        r"/etc/passwd",
        r"~?/\.ssh(/.*)?",
        r"~?/\.aws(/.*)?",
        r"~?/\.gnupg(/.*)?",
        r"~?/\.gemini(/.*)?",
    ]

    def __init__(self, permissions: Optional[ToolPermissionsConfig] = None):
        self.permissions = permissions or ToolPermissionsConfig()

    def validate_command(self, command: str) -> Tuple[bool, Optional[str]]:
        """Verify whether a shell command is permitted."""
        if not self.permissions.terminal.enabled:
            return False, "Terminal execution is disabled by configuration"

        cleaned = command.strip()

        # Check git push restriction
        if re.search(r"\bgit\s+push\b", cleaned):
            if not self.permissions.git.allow_push:
                return False, "Git push operations are strictly prohibited"

        # Check explicit blocked commands
        for blocked in self.permissions.terminal.blocked_commands:
            if blocked in cleaned:
                return False, f"Command contains explicitly blocked phrase: '{blocked}'"

        # Check regex danger patterns
        for pattern in self.DANGEROUS_COMMAND_PATTERNS:
            if pattern == r"\bgit\s+push\b":
                continue
            if re.search(pattern, cleaned):
                return False, f"Command violates safety policy: matches pattern '{pattern}'"

        return True, None

    def validate_path(self, target_path: Path, workspace: Path, is_write: bool = False) -> Tuple[bool, Optional[str]]:
        """Ensure file access does not escape workspace or access sensitive directories."""
        workspace_resolved = workspace.resolve()
        target_resolved = target_path.resolve()

        # Check sensitive path patterns
        path_str = str(target_resolved)
        for pattern in self.SENSITIVE_PATH_PATTERNS:
            if re.search(pattern, path_str):
                return False, f"Access to sensitive path '{path_str}' is denied"

        # Ensure path is within workspace
        try:
            target_resolved.relative_to(workspace_resolved)
        except ValueError:
            return False, f"Path '{path_str}' escapes workspace boundary '{workspace_resolved}'"

        # Check read / write permissions
        if is_write and not self.permissions.filesystem.write:
            return False, "Filesystem write access is disabled by configuration"
        if not is_write and not self.permissions.filesystem.read:
            return False, "Filesystem read access is disabled by configuration"

        return True, None

    def generate_opencode_permissions(self) -> Dict[str, Any]:
        """Convert harness permissions into OpenCode-compatible permission configuration."""
        perm_config: Dict[str, Any] = {}

        # Filesystem
        perm_config["read"] = "allow" if self.permissions.filesystem.read else "deny"
        perm_config["edit"] = "allow" if self.permissions.filesystem.write else "deny"

        # Terminal / bash
        if not self.permissions.terminal.enabled:
            perm_config["bash"] = "deny"
        else:
            # OpenCode supports rules
            perm_config["bash"] = "allow"

        return perm_config
