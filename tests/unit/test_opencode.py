"""Unit tests for OpenCode output parsing and backend abstraction."""

from pathlib import Path
from harness.models import AgentMode
from harness.opencode.base import AgentResponse
from harness.opencode.mock import MockBackend
from harness.opencode.parser import OpenCodeOutputParser


def test_parser_with_stream_events():
    stream_output = (
        '{"type":"step_start","timestamp":1789047308002,"sessionID":"ses_12345"}\n'
        '{"type":"text","sessionID":"ses_12345","part":{"type":"text","text":"Fixing "}}\n'
        '{"type":"text","sessionID":"ses_12345","part":{"type":"text","text":"the bug."}}\n'
        '{"type":"tool-call","toolName":"edit","input":{"path":"app/main.py"}}\n'
        '{"type":"step_finish","sessionID":"ses_12345","part":{"tokens":{"input":1200,"output":250,"reasoning":50,"total":1450},"cost":0.001}}\n'
    )

    resp = OpenCodeOutputParser.parse_stream(stream_output)
    assert resp.session_id == "ses_12345"
    assert resp.text == "Fixing the bug."
    assert resp.tool_calls.get("edit") == 1
    assert "app/main.py" in resp.files_modified
    assert resp.token_usage.total_tokens == 1450
    assert resp.token_usage.cost == 0.001


def test_parser_with_error_event():
    stream_output = (
        '{"type":"error","sessionID":"ses_err","error":{"name":"AuthError","data":{"message":"Invalid API key"}}}\n'
    )
    resp = OpenCodeOutputParser.parse_stream(stream_output)
    assert resp.session_id == "ses_err"
    assert resp.error_message == "Invalid API key"


def test_mock_backend_execution(tmp_path):
    backend = MockBackend()
    assert backend.is_available() is True

    # Setup dummy project file
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    main_py = app_dir / "main.py"
    main_py.write_text("def login(username: str):\n    raise HTTPException(status_code=500)", encoding="utf-8")

    # Turn 1: Initial implementation
    resp1 = backend.execute_turn("Implement login endpoint", tmp_path, mode=AgentMode.DEVELOPER)
    assert resp1.exit_code == 0
    assert resp1.token_usage.is_available is True

    # Turn 2: Self-correction on test failure feedback
    feedback_prompt = (
        "TEST EXECUTION RESULT\n"
        "Status: FAILED\n"
        "Failures: 1. test_invalid_token: expected 401, got 500"
    )
    resp2 = backend.execute_turn(feedback_prompt, tmp_path, mode=AgentMode.DEVELOPER)
    assert resp2.exit_code == 0
    # Check that main.py now has 401
    assert "status_code=401" in main_py.read_text(encoding="utf-8")
