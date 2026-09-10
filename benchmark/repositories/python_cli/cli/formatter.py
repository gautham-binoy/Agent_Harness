"""Output formatters for CLI application."""

from __future__ import annotations

import json
from typing import Any, Dict, List


class OutputFormatter:
    """Formats structured outputs for terminal display."""

    @staticmethod
    def to_json(data: Any) -> str:
        return json.dumps(data, indent=2)

    @staticmethod
    def to_csv_lines(items: List[Dict[str, Any]]) -> List[str]:
        if not items:
            return []
        headers = list(items[0].keys())
        lines = [",".join(headers)]
        for item in items:
            lines.append(",".join(str(item.get(h, "")) for h in headers))
        return lines
