"""Hidden validation test suite for Python CLI sample repository.

Evaluates boundary parsing, quotation handling, and empty data structures.
"""

import pytest
from cli.parser import CliParser
from cli.formatter import OutputFormatter


def test_hidden_parser_multiple_equals():
    parser = CliParser()
    res = parser.parse_key_value(["url=https://example.com?a=1&b=2"])
    assert res.get("url") == "https://example.com?a=1&b=2"


def test_hidden_parser_unicode_json():
    parser = CliParser()
    res = parser.parse_json_input('{"greeting": "こんにちは"}')
    assert res.get("greeting") == "こんにちは"


def test_hidden_formatter_empty_items():
    csv_lines = OutputFormatter.to_csv_lines([])
    assert csv_lines == []
