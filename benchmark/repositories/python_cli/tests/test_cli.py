"""Tests for Python CLI sample app."""

import pytest
from cli.parser import CliParser
from cli.formatter import OutputFormatter
from cli.commands import CommandDispatcher


def test_parse_key_value():
    parser = CliParser()
    res = parser.parse_key_value(["env=prod", "debug=true"])
    assert res == {"env": "prod", "debug": "true"}


def test_parse_json_valid():
    parser = CliParser()
    res = parser.parse_json_input('{"action": "deploy"}')
    assert res["action"] == "deploy"


def test_parse_json_invalid():
    parser = CliParser()
    with pytest.raises(ValueError, match="Malformed"):
        parser.parse_json_input("{bad json")


def test_command_status():
    dispatcher = CommandDispatcher()
    status = dispatcher.handle_status()
    assert status["status"] == "active"


def test_formatter_csv():
    items = [{"id": 1, "name": "Task A"}, {"id": 2, "name": "Task B"}]
    csv_lines = OutputFormatter.to_csv_lines(items)
    assert len(csv_lines) == 3
    assert csv_lines[0] == "id,name"
