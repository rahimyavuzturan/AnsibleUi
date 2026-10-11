"""Saglik uclari testleri."""

from __future__ import annotations

from app.main import create_app
from fastapi.testclient import TestClient


def test_healthz_ok_doner() -> None:
    with TestClient(create_app()) as client:
        yanit = client.get("/healthz")
    assert yanit.status_code == 200
    assert yanit.json()["status"] == "ok"


def test_readyz_ok_doner() -> None:
    with TestClient(create_app()) as client:
        yanit = client.get("/readyz")
    assert yanit.status_code == 200
    assert yanit.json()["status"] == "ok"
