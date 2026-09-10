"""Parser for OpenCode streaming JSON outputs and exported session data."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple
from harness.logging_config import logger
from harness.models import TokenUsage
from harness.opencode.base import AgentResponse


class OpenCodeOutputParser:
    """Parses streaming output and exported sessions from OpenCode CLI."""

    @staticmethod
    def parse_stream(stdout: str) -> AgentResponse:
        """Parse newline-delimited JSON events produced by `opencode run --format json`."""
        texts: List[str] = []
        tool_calls: Dict[str, int] = {}
        files_modified: List[str] = []
        token_usage = TokenUsage()
        session_id: Optional[str] = None
        error_msg: Optional[str] = None
        events: List[Dict[str, Any]] = []

        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            # Try to parse line as JSON
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                # If not JSON, it might be raw terminal output or log line
                continue

            events.append(event)
            event_type = event.get("type", "")

            # Capture session ID
            if "sessionID" in event and not session_id:
                session_id = event["sessionID"]

            # Handle text deltas
            if event_type == "text":
                part = event.get("part", {})
                if isinstance(part, dict) and "text" in part:
                    texts.append(part["text"])
                elif "text" in event:
                    texts.append(event["text"])

            # Handle tool calls
            elif event_type in ("tool-call", "tool_call", "builtin_tool_call"):
                tool_name = (
                    event.get("toolName")
                    or event.get("name")
                    or event.get("part", {}).get("name")
                    or "unknown"
                )
                tool_calls[tool_name] = tool_calls.get(tool_name, 0) + 1

                # Check for file path in tool input
                input_data = event.get("input") or event.get("part", {}).get("input")
                if isinstance(input_data, dict) and "path" in input_data:
                    files_modified.append(input_data["path"])

            # Handle step_finish with tokens
            elif event_type in ("step_finish", "step-finish"):
                part = event.get("part", {})
                tokens_info = part.get("tokens") or event.get("tokens")
                if isinstance(tokens_info, dict):
                    token_usage.input_tokens = tokens_info.get("input")
                    token_usage.output_tokens = tokens_info.get("output")
                    token_usage.reasoning_tokens = tokens_info.get("reasoning", 0)
                    token_usage.total_tokens = tokens_info.get("total")
                    token_usage.is_available = True

                cost_val = part.get("cost") or event.get("cost")
                if cost_val is not None:
                    try:
                        token_usage.cost = float(cost_val)
                    except (ValueError, TypeError):
                        pass

            # Handle error events
            elif event_type == "error":
                err_data = event.get("error", {})
                if isinstance(err_data, dict):
                    msg = err_data.get("data", {}).get("message") or err_data.get("name") or str(err_data)
                    error_msg = msg
                else:
                    error_msg = str(err_data)

        full_text = "".join(texts).strip()

        # If no json text was accumulated, fallback to non-json stdout text
        if not full_text and not error_msg:
            non_json_lines = [
                l for l in stdout.splitlines() if not l.strip().startswith("{")
            ]
            full_text = "\n".join(non_json_lines).strip()

        return AgentResponse(
            text=full_text,
            tool_calls=tool_calls,
            files_modified=sorted(list(set(files_modified))),
            token_usage=token_usage,
            session_id=session_id,
            error_message=error_msg,
            raw_events=events,
        )

    @staticmethod
    def parse_export_session(export_json_str: str) -> Tuple[TokenUsage, List[str], Dict[str, int]]:
        """Parse full session JSON from `opencode export <session_id>`."""
        token_usage = TokenUsage()
        files_modified: List[str] = []
        tool_calls: Dict[str, int] = {}

        try:
            # opencode export might output "Exporting session: ses_..." before the JSON
            idx = export_json_str.find("{")
            if idx == -1:
                return TokenUsage.unavailable(), [], {}
            data = json.loads(export_json_str[idx:])

            info = data.get("info", {})
            tokens = info.get("tokens", {})
            if tokens:
                token_usage.input_tokens = tokens.get("input")
                token_usage.output_tokens = tokens.get("output")
                token_usage.reasoning_tokens = tokens.get("reasoning", 0)
                token_usage.total_tokens = (token_usage.input_tokens or 0) + (token_usage.output_tokens or 0)
                token_usage.is_available = True

            cost = info.get("cost")
            if cost is not None:
                token_usage.cost = float(cost)

            summary = info.get("summary", {})
            # Files changed count or list
            # We can also parse steps/messages for tool calls if present
            steps = data.get("steps", []) or data.get("messages", [])
            for step in steps:
                for part in step.get("parts", []):
                    if part.get("type") in ("tool-call", "tool_call"):
                        t_name = part.get("name", "unknown")
                        tool_calls[t_name] = tool_calls.get(t_name, 0) + 1
        except Exception as e:
            logger.warning(f"Could not parse exported session: {e}")
            return TokenUsage.unavailable(), [], {}

        return token_usage, files_modified, tool_calls
