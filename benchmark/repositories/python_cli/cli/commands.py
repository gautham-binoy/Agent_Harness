"""Command runner for Python CLI app."""

from __future__ import annotations

from typing import Any, Dict
from cli.parser import CliParser
from cli.formatter import OutputFormatter


class CommandDispatcher:
    """Dispatches CLI subcommands."""

    def __init__(self):
        self.parser = CliParser()
        self.formatter = OutputFormatter()

    def handle_status(self) -> Dict[str, str]:
        return {"status": "active", "version": "1.0.0"}

    def handle_process(self, json_payload: str) -> str:
        data = self.parser.parse_json_input(json_payload)
        return self.formatter.to_json({"processed": True, "data": data})
