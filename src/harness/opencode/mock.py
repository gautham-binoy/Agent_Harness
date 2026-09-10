"""Mock agent backend for offline testing, dry-runs, and demonstrations."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from harness.logging_config import logger
from harness.models import AgentMode, TokenUsage, ToolPermissionsConfig
from harness.opencode.base import AgentBackend, AgentResponse


class MockBackend(AgentBackend):
    """Simulated coding agent capable of realistic multi-turn iterative self-correction.
    
    Models real LLM dynamics:
    - Zero-shot (Turn 1): Solves easy tasks reliably, but misses edge cases on medium/hard tasks.
    - Multi-turn with feedback (Turn 2+): Extracts failure stack trace details and repairs implementation.
    """

    def __init__(self, simulate_token_cost: bool = True):
        self.simulate_token_cost = simulate_token_cost
        self.turn_count = 0

    def is_available(self) -> bool:
        return True

    def execute_turn(
        self,
        prompt: str,
        workspace: Path,
        mode: AgentMode = AgentMode.DEVELOPER,
        permissions: Optional[ToolPermissionsConfig] = None,
        timeout: int = 120,
        session_id: Optional[str] = None,
    ) -> AgentResponse:
        """Simulate agent inspecting code, modifying files, and fixing errors upon feedback."""
        self.turn_count += 1
        is_correction_turn = (
            "TEST EXECUTION RESULT" in prompt
            or "FAILED" in prompt
            or "Failures:" in prompt
            or "Fix the implementation" in prompt
        )

        # Detect difficulty from prompt
        is_easy = "Difficulty: easy" in prompt or "difficulty: easy" in prompt.lower()
        is_hard = "Difficulty: hard" in prompt or "difficulty: hard" in prompt.lower()

        files_modified = []
        response_text = ""

        if is_correction_turn:
            # Turn 2+: Fix the failures based on feedback
            logger.info(f"[MockBackend] Self-correction turn {self.turn_count} in {workspace.name}. Applying full fix.")
            response_text = (
                "I analyzed the test failure feedback and stack trace.\n"
                "Refactoring the implementation to handle boundary conditions and assertion requirements."
            )
            files_modified = self._apply_complete_fix(workspace)
        else:
            # Turn 1: Initial implementation attempt
            logger.info(f"[MockBackend] Turn 1 initial attempt in {workspace.name}")
            if is_easy:
                # Easy tasks succeed on turn 1
                response_text = "Inspected repository. Implementing full fix for requested task."
                files_modified = self._apply_complete_fix(workspace)
            else:
                # Medium & Hard tasks make a partial attempt (misses edge case or raises failure)
                response_text = "Inspected repository. Implementing initial solution."
                files_modified = self._apply_partial_fix(workspace)

        tokens = TokenUsage(
            input_tokens=1420 + self.turn_count * 350,
            output_tokens=310 + self.turn_count * 90,
            reasoning_tokens=180,
            total_tokens=1730 + self.turn_count * 440,
            cost=round(0.00045 * self.turn_count, 6),
            is_available=True,
        )

        tool_calls = {
            "read": 3 + self.turn_count,
            "edit": len(files_modified) if files_modified else 1,
            "bash": 1,
        }

        return AgentResponse(
            text=response_text,
            tool_calls=tool_calls,
            files_modified=files_modified,
            token_usage=tokens,
            session_id=session_id or f"mock_session_{self.turn_count}",
            exit_code=0,
        )

    def _apply_partial_fix(self, workspace: Path) -> list[str]:
        """Apply a partial attempt that leaves edge cases failing."""
        modified = []
        main_py = workspace / "app" / "main.py"
        cli_parser = workspace / "cli" / "parser.py"
        node_index = workspace / "index.js"

        if main_py.exists():
            txt = main_py.read_text(encoding="utf-8")
            txt += "\n# Partial implementation attempt\n"
            main_py.write_text(txt, encoding="utf-8")
            modified.append(str(main_py.relative_to(workspace)))

        if cli_parser.exists():
            txt = cli_parser.read_text(encoding="utf-8")
            txt += "\n# Partial parsing attempt\n"
            cli_parser.write_text(txt, encoding="utf-8")
            modified.append(str(cli_parser.relative_to(workspace)))

        if node_index.exists():
            txt = node_index.read_text(encoding="utf-8")
            txt += "\n// Partial attempt\n"
            node_index.write_text(txt, encoding="utf-8")
            modified.append(str(node_index.relative_to(workspace)))

        return modified

    def _apply_complete_fix(self, workspace: Path) -> list[str]:
        """Apply complete, working fix satisfying public and hidden tests."""
        modified = []

        # 1. FastAPI App
        main_py = workspace / "app" / "main.py"
        if main_py.exists():
            content = main_py.read_text(encoding="utf-8")
            # Fix 500 to 401
            content = re.sub(r"status_code\s*=\s*500", "status_code=401", content)
            # Fix missing password
            if "if False:" in content and "password" in content:
                content = content.replace("if False:", "if not req.password:")
            # Fix whitespace title
            if "if False:" in content and "title" in content:
                content = content.replace("if False:", "if not item.title.strip():")
            # Fix missing 404
            if "if False:" in content and "item_id" in content:
                content = content.replace("if False:", "if item_id not in ITEMS_DB:")
            # Fix pagination
            if "return items\n" in content and "items[skip" not in content:
                content = content.replace("return items\n", "return items[skip : skip + limit]\n")
            # Fix root endpoint
            if "status_code=503" in content:
                content = content.replace("raise HTTPException(status_code=503)", 'return {"status": "ok", "service": "TaskFlow"}')
            # Fix item create
            if "raise HTTPException(status_code=500)" in content:
                content = content.replace("raise HTTPException(status_code=500)", "return new_item")
            # Fix login token
            if '"token":' not in content and '"username": req.username' in content:
                content = content.replace('"username": req.username', '"token": f"mock_token_{req.username}", "username": req.username')

            main_py.write_text(content, encoding="utf-8")
            modified.append(str(main_py.relative_to(workspace)))

        # 2. Python CLI
        cli_parser = workspace / "cli" / "parser.py"
        if cli_parser.exists():
            p_txt = cli_parser.read_text(encoding="utf-8")
            p_txt = p_txt.replace("except (AttributeError, KeyError) as e:", "except json.JSONDecodeError as e:")
            p_txt = p_txt.replace("k] = v", "k.strip()] = v.strip()")
            p_txt = p_txt.replace("raise NotImplementedError", "return json.loads(raw)")
            cli_parser.write_text(p_txt, encoding="utf-8")
            modified.append(str(cli_parser.relative_to(workspace)))

        cli_formatter = workspace / "cli" / "formatter.py"
        if cli_formatter.exists():
            f_txt = cli_formatter.read_text(encoding="utf-8")
            f_txt = f_txt.replace("return None", "return []")
            f_txt = f_txt.replace('raise NotImplementedError("csv")', "return lines")
            cli_formatter.write_text(f_txt, encoding="utf-8")
            modified.append(str(cli_formatter.relative_to(workspace)))

        cli_commands = workspace / "cli" / "commands.py"
        if cli_commands.exists():
            c_txt = cli_commands.read_text(encoding="utf-8")
            c_txt = c_txt.replace('raise NotImplementedError("status")', 'return {"status": "active", "version": "1.0.0"}')
            c_txt = c_txt.replace("raise NotImplementedError", "return self.formatter.to_json({'processed': True, 'data': data})")
            cli_commands.write_text(c_txt, encoding="utf-8")
            modified.append(str(cli_commands.relative_to(workspace)))

        # 3. Node App
        node_index = workspace / "index.js"
        if node_index.exists():
            n_txt = node_index.read_text(encoding="utf-8")
            n_txt = n_txt.replace("if (false)", "if (numbers.length === 0)")
            n_txt = n_txt.replace('const cleaned = qs;', 'const cleaned = qs.startsWith("?") ? qs.slice(1) : qs;')
            n_txt = n_txt.replace("return {};", "return params;")
            n_txt = n_txt.replace("throw new Error('Not implemented'); ", "")
            node_index.write_text(n_txt, encoding="utf-8")
            modified.append(str(node_index.relative_to(workspace)))

        # 4. Tests files (for test writing tasks)
        fastapi_tests = workspace / "tests" / "test_main.py"
        if fastapi_tests.exists():
            t_txt = fastapi_tests.read_text(encoding="utf-8")
            if "# Missing test" in t_txt:
                t_txt += "\n\ndef test_additional_validation():\n    assert True\n"
                fastapi_tests.write_text(t_txt, encoding="utf-8")
                modified.append(str(fastapi_tests.relative_to(workspace)))

        return modified
