"""Saglik ve hazir olma uclari.

Kubernetes liveness/readiness problari bu uclari kullanir.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Saglik kontrolu yaniti."""

    status: Literal["ok"]
    version: str


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Surecin ayakta oldugunu bildirir (liveness)."""
    return HealthResponse(status="ok", version="0.1.0")


@router.get("/readyz", response_model=HealthResponse)
async def readyz() -> HealthResponse:
    """Surecin istek almaya hazir oldugunu bildirir (readiness).

    Not: Veritabani ve depo kontrolleri WP-22 ve WP-30 ile eklenecek.
    """
    return HealthResponse(status="ok", version="0.1.0")
