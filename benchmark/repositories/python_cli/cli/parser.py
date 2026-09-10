"""CLI input parsing and validation."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


class CliParser:
    """Parses command-line strings and payloads."""

    def parse_key_value(self, args: List[str]) -> Dict[str, str]:
        result = {}
        for arg in args:
            if "=" in arg:
                k, v = arg.split("=", 1)
                result[k.strip()] = v.strip()
        return result

    def parse_json_input(self, raw: str) -> Dict[str, Any]:
        if not raw or not raw.strip():
            raise ValueError("Input cannot be empty")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed JSON payload: {e}")
