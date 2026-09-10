"""FastAPI Sample Application for Benchmark Testing."""

from __future__ import annotations

from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

app = FastAPI(title="TaskFlow API", version="1.0.0")

# In-memory store
USERS_DB = {"admin": "secret123", "alice": "wonderland"}
ITEMS_DB: Dict[int, Dict] = {
    1: {"id": 1, "title": "Setup repository", "completed": True},
    2: {"id": 2, "title": "Implement authentication", "completed": False},
}


class LoginRequest(BaseModel):
    username: str
    password: Optional[str] = None


class ItemCreate(BaseModel):
    title: str
    completed: bool = False


@app.get("/")
def read_root():
    return {"status": "ok", "service": "TaskFlow"}


@app.post("/login")
def login(req: LoginRequest):
    if not req.password:
        raise HTTPException(status_code=400, detail="Password is required")
    expected = USERS_DB.get(req.username)
    if not expected or expected != req.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": f"mock_token_{req.username}", "username": req.username}


@app.get("/items")
def list_items(skip: int = 0, limit: int = 10):
    items = list(ITEMS_DB.values())
    return items[skip : skip + limit]


@app.get("/items/{item_id}")
def get_item(item_id: int):
    if item_id not in ITEMS_DB:
        raise HTTPException(status_code=404, detail="Item not found")
    return ITEMS_DB[item_id]


@app.post("/items", status_code=201)
def create_item(item: ItemCreate):
    if not item.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    new_id = max(ITEMS_DB.keys(), default=0) + 1
    new_item = {"id": new_id, "title": item.title, "completed": item.completed}
    ITEMS_DB[new_id] = new_item
    return new_item
