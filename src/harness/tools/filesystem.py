"""Workspace-constrained filesystem operations."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from harness.tools.permissions import PermissionManager, SecurityException


class SafeFileSystem:
    """Provides workspace-bounded file reading, writing, and listing."""

    def __init__(self, workspace: Path, permissions: Optional[PermissionManager] = None):
        self.workspace = workspace.resolve()
        self.permissions = permissions or PermissionManager()

    def read_file(self, rel_path: str | Path) -> str:
        target = (self.workspace / rel_path).resolve()
        ok, err = self.permissions.validate_path(target, self.workspace, is_write=False)
        if not ok:
            raise SecurityException(err)
        return target.read_text(encoding="utf-8")

    def write_file(self, rel_path: str | Path, content: str) -> None:
        target = (self.workspace / rel_path).resolve()
        ok, err = self.permissions.validate_path(target, self.workspace, is_write=True)
        if not ok:
            raise SecurityException(err)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def list_files(self, rel_dir: str = ".") -> List[str]:
        target = (self.workspace / rel_dir).resolve()
        ok, err = self.permissions.validate_path(target, self.workspace, is_write=False)
        if not ok:
            raise SecurityException(err)
        files = []
        for p in target.glob("**/*"):
            if p.is_file():
                try:
                    files.append(str(p.relative_to(self.workspace)))
                except ValueError:
                    pass
        return sorted(files)
