"""Tests for FastAPI sample app."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_login_success():
    res = client.post("/login", json={"username": "admin", "password": "secret123"})
    assert res.status_code == 200
    assert "token" in res.json()


def test_login_invalid_password():
    res = client.post("/login", json={"username": "admin", "password": "wrongpassword"})
    assert res.status_code == 401


def test_login_missing_password():
    res = client.post("/login", json={"username": "admin"})
    assert res.status_code == 400


def test_list_items():
    res = client.get("/items")
    assert res.status_code == 200
    assert len(res.json()) >= 2


def test_create_item_success():
    res = client.post("/items", json={"title": "New Task", "completed": False})
    assert res.status_code == 201
    assert res.json()["title"] == "New Task"


def test_create_item_empty_title():
    res = client.post("/items", json={"title": "   "})
    assert res.status_code == 400
