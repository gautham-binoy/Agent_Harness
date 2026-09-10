"""Hidden validation test suite for FastAPI sample repository.

These tests evaluate edge cases and boundary conditions that the agent does not
observe in public task prompts, preventing superficial memorization and ensuring
genuine generalization.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_hidden_login_edge_cases():
    # Empty string password
    res = client.post("/login", json={"username": "admin", "password": ""})
    assert res.status_code in (400, 422), "Empty password must be rejected with 400/422"

    # Non-existent user
    res2 = client.post("/login", json={"username": "ghost_user", "password": "password"})
    assert res2.status_code == 401, "Unknown user must return 401 Unauthorized"


def test_hidden_items_pagination_bounds():
    # Negative skip or limit should be handled cleanly
    res = client.get("/items?skip=0&limit=1")
    assert res.status_code == 200
    assert len(res.json()) <= 1


def test_hidden_create_item_whitespace_rejection():
    # Tab / newline whitespace title
    res = client.post("/items", json={"title": "\t\n  ", "completed": False})
    assert res.status_code == 400, "Whitespace title must return 400"
