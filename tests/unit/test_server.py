"""Unit tests for FastAPI dashboard and REST endpoints."""

from fastapi.testclient import TestClient
from harness.server import app

client = TestClient(app)


def test_dashboard_html_view():
    res = client.get("/")
    assert res.status_code == 200
    assert "Adaptive Coding Agent Harness" in res.text


def test_api_runs_list():
    res = client.get("/api/runs")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_api_metrics():
    res = client.get("/api/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "success_rate" in data
    assert "total_tasks" in data


def test_api_benchmarks():
    res = client.get("/api/benchmarks")
    assert res.status_code == 200
    tasks = res.json()
    assert len(tasks) == 30
