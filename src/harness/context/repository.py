"""Inspects repositories to generate compact, structured context for coding agents."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set


class RepositoryInspector:
    """Inspects a repository workspace to extract metadata without bloating context."""

    IGNORE_DIRS: Set[str] = {
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "dist",
        ".next",
        ".idea",
        ".vscode",
        ".gemini",
    }

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()

    def detect_languages(self) -> List[str]:
        """Detect primary programming languages used in the repository."""
        langs = set()
        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in (".py", ".pyw"):
                    langs.add("Python")
                elif ext in (".js", ".jsx", ".mjs", ".cjs"):
                    langs.add("JavaScript")
                elif ext in (".ts", ".tsx"):
                    langs.add("TypeScript")
                elif ext in (".go",):
                    langs.add("Go")
                elif ext in (".rs",):
                    langs.add("Rust")
                elif ext in (".java",):
                    langs.add("Java")
        return sorted(list(langs)) or ["Unknown"]

    def detect_package_manager(self) -> str:
        """Detect package manager configuration."""
        if (self.workspace / "poetry.lock").exists():
            return "poetry"
        if (self.workspace / "Pipfile").exists():
            return "pipenv"
        if (self.workspace / "requirements.txt").exists() or (self.workspace / "pyproject.toml").exists():
            return "pip"
        if (self.workspace / "pnpm-lock.yaml").exists():
            return "pnpm"
        if (self.workspace / "yarn.lock").exists():
            return "yarn"
        if (self.workspace / "package.json").exists():
            return "npm"
        if (self.workspace / "Cargo.toml").exists():
            return "cargo"
        if (self.workspace / "go.mod").exists():
            return "go modules"
        return "Standard / None"

    def detect_framework(self) -> str:
        """Detect web/application framework."""
        pyproject = self.workspace / "pyproject.toml"
        reqs = self.workspace / "requirements.txt"
        pkg_json = self.workspace / "package.json"

        texts = []
        for p in (pyproject, reqs, pkg_json):
            if p.exists():
                try:
                    texts.append(p.read_text(encoding="utf-8").lower())
                except Exception:
                    pass

        combined = " ".join(texts)
        if "fastapi" in combined:
            return "FastAPI application"
        if "flask" in combined:
            return "Flask application"
        if "django" in combined:
            return "Django application"
        if "express" in combined:
            return "Express.js application"
        if "next" in combined:
            return "Next.js application"
        if "react" in combined:
            return "React application"
        if "click" in combined or "typer" in combined or "argparse" in combined:
            return "Python CLI tool"

        # Check directory structure
        if (self.workspace / "app" / "main.py").exists():
            return "FastAPI/Python Web App"
        if (self.workspace / "cli.py").exists() or (self.workspace / "src" / "cli.py").exists():
            return "Python CLI"

        return "Generic software project"

    def detect_test_framework(self) -> str:
        """Detect test framework and default test command."""
        # Check python test configs
        if (
            (self.workspace / "pytest.ini").exists()
            or (self.workspace / "conftest.py").exists()
            or (self.workspace / "tests").exists()
        ):
            return "pytest"
        if (self.workspace / "package.json").exists():
            return "npm test"
        return "pytest / standard runner"

    def detect_linter(self) -> Optional[str]:
        """Detect configured linter."""
        if (self.workspace / "ruff.toml").exists() or (self.workspace / ".ruff.toml").exists():
            return "ruff"
        if (self.workspace / ".flake8").exists():
            return "flake8"
        if (self.workspace / ".eslintrc.json").exists() or (self.workspace / ".eslintrc.js").exists():
            return "eslint"
        # Check pyproject.toml for ruff or flake8
        pyproject = self.workspace / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(encoding="utf-8")
                if "[tool.ruff]" in content:
                    return "ruff"
            except Exception:
                pass
        return "ruff (if available)"

    def get_git_status(self) -> str:
        """Get brief git status of the repository."""
        try:
            res = subprocess.run(
                ["git", "status", "--short"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                lines = res.stdout.strip().splitlines()
                if not lines:
                    return "clean working tree"
                return f"{len(lines)} modified/untracked files"
        except Exception:
            pass
        return "git not available or non-git directory"

    def find_important_files(self, limit: int = 15) -> List[str]:
        """Identify key entrypoints and architectural files."""
        important = []
        candidates = [
            "README.md",
            "pyproject.toml",
            "requirements.txt",
            "package.json",
            "Dockerfile",
            "app/main.py",
            "app/routes.py",
            "app/models.py",
            "app/auth.py",
            "src/main.py",
            "src/index.js",
            "src/cli.py",
            "cli.py",
            "main.py",
            "tests/test_main.py",
            "tests/conftest.py",
        ]

        for cand in candidates:
            if (self.workspace / cand).exists():
                important.append(cand)

        # Add top-level test files
        tests_dir = self.workspace / "tests"
        if tests_dir.exists():
            for t in tests_dir.glob("test_*.py"):
                rel = str(t.relative_to(self.workspace))
                if rel not in important:
                    important.append(rel)

        return important[:limit]

    def build_directory_tree(self, max_depth: int = 3, max_files: int = 30) -> str:
        """Generate a concise, ASCII directory tree."""
        lines = []
        count = 0

        def _traverse(current: Path, depth: int, prefix: str):
            nonlocal count
            if depth > max_depth or count >= max_files:
                return

            try:
                entries = sorted(
                    [e for e in current.iterdir() if e.name not in self.IGNORE_DIRS],
                    key=lambda x: (not x.is_dir(), x.name.lower()),
                )
            except PermissionError:
                return

            for i, entry in enumerate(entries):
                if count >= max_files:
                    lines.append(f"{prefix}... (truncated)")
                    break

                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "
                sub_prefix = "    " if is_last else "│   "

                count += 1
                if entry.is_dir():
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    _traverse(entry, depth + 1, prefix + sub_prefix)
                else:
                    lines.append(f"{prefix}{connector}{entry.name}")

        _traverse(self.workspace, 1, "")
        return "\n".join(lines) if lines else "Empty repository"

    def get_readme_excerpt(self, max_lines: int = 10) -> Optional[str]:
        """Extract a short excerpt from README.md if present."""
        readme = self.workspace / "README.md"
        if not readme.exists():
            return None
        try:
            lines = readme.read_text(encoding="utf-8").strip().splitlines()
            return "\n".join(lines[:max_lines])
        except Exception:
            return None

    def generate_summary(self) -> str:
        """Produce a compact, high-value repository summary."""
        project = self.detect_framework()
        languages = ", ".join(self.detect_languages())
        pkg_manager = self.detect_package_manager()
        test_framework = self.detect_test_framework()
        linter = self.detect_linter() or "None"
        git_status = self.get_git_status()
        important_files = "\n".join(f"- {f}" for f in self.find_important_files())
        tree = self.build_directory_tree(max_depth=2, max_files=20)
        readme_excerpt = self.get_readme_excerpt()

        summary_parts = [
            "### REPOSITORY CONTEXT",
            f"**Project**: {project}",
            f"**Languages**: {languages}",
            f"**Package manager**: {pkg_manager}",
            f"**Test framework**: {test_framework}",
            f"**Linter**: {linter}",
            f"**Git status**: {git_status}",
            "",
            "**Important Files**:",
            important_files if important_files else "- None detected",
            "",
            "**Directory Overview**:",
            "```text",
            tree,
            "```",
        ]

        if readme_excerpt:
            summary_parts.extend([
                "",
                "**README Excerpt**:",
                f"> {readme_excerpt.replace(chr(10), chr(10) + '> ')}",
            ])

        return "\n".join(summary_parts)
