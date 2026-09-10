"""Unit tests for repository context, tools, and security permissions."""

import pytest
from pathlib import Path
from harness.agents import get_agent_mode, DeveloperMode, TestWriterMode, MigrationMode
from harness.context.repository import RepositoryInspector
from harness.models import AgentMode, ToolPermissionsConfig
from harness.tools.filesystem import SafeFileSystem
from harness.tools.permissions import PermissionManager, SecurityException
from harness.tools.terminal import SafeTerminal


def test_agent_modes():
    dev = get_agent_mode(AgentMode.DEVELOPER)
    assert isinstance(dev, DeveloperMode)
    assert "Developer Mode" in dev.get_system_instructions()

    tw = get_agent_mode("test_writer")
    assert isinstance(tw, TestWriterMode)

    mig = get_agent_mode("migration")
    assert isinstance(mig, MigrationMode)


def test_repository_inspector(tmp_path):
    # Setup dummy FastAPI repository
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\npytest", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test API Service\nA sample FastAPI app.", encoding="utf-8")

    inspector = RepositoryInspector(tmp_path)
    assert "Python" in inspector.detect_languages()
    assert inspector.detect_package_manager() == "pip"
    assert "FastAPI" in inspector.detect_framework()

    summary = inspector.generate_summary()
    assert "FastAPI" in summary
    assert "Python" in summary
    assert "main.py" in summary


def test_permission_manager_command_blocking():
    pm = PermissionManager()

    # Safe commands
    ok, err = pm.validate_command("pytest -q")
    assert ok is True
    assert err is None

    ok, err = pm.validate_command("python -m ruff check .")
    assert ok is True

    # Dangerous commands
    ok, err = pm.validate_command("rm -rf /")
    assert ok is False
    assert "matches pattern" in err or "blocked" in err

    ok, err = pm.validate_command("git push origin main")
    assert ok is False
    assert "Git push" in err or "blocked" in err

    ok, err = pm.validate_command("mkfs.ext4 /dev/sda1")
    assert ok is False


def test_permission_manager_path_validation(tmp_path):
    pm = PermissionManager()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    safe_file = workspace / "test.py"
    safe_file.write_text("print('hello')", encoding="utf-8")

    # Safe inside workspace
    ok, err = pm.validate_path(safe_file, workspace, is_write=False)
    assert ok is True

    # Escapes workspace
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret", encoding="utf-8")
    ok, err = pm.validate_path(outside_file, workspace, is_write=False)
    assert ok is False
    assert "escapes workspace" in err

    # Sensitive path
    sensitive = Path("/etc/shadow")
    ok, err = pm.validate_path(sensitive, workspace, is_write=False)
    assert ok is False


def test_safe_filesystem(tmp_path):
    fs = SafeFileSystem(tmp_path)
    fs.write_file("nested/module.py", "x = 42\n")
    content = fs.read_file("nested/module.py")
    assert "x = 42" in content

    files = fs.list_files()
    assert "nested/module.py" in files

    # Attempt path traversal
    with pytest.raises(SecurityException):
        fs.read_file("../../../etc/passwd")
