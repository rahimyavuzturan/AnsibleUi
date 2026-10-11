"""Yonetici onizlemesi uclari.

Gecici kapsam: bu uclar WP-30/WP-32 ile gelecek kalici API sozlesmesinin
(``docs/09-api-contract.md``) yerine gecmez. Yalnizca uretim disi ortamlarda
baglanir (bkz. ``app.main.create_app``).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.config import Settings, get_settings
from app.services.preview_service import (
    DocumentView,
    RepoSummary,
    build_document_view,
    scan_repository,
)

router = APIRouter(prefix="/api/preview", tags=["preview"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/summary", response_model=RepoSummary)
async def summary(settings: SettingsDep) -> RepoSummary:
    """Depo genelinde ozet sayilar ve dosya listesi."""
    return scan_repository(settings.repo_path)


@router.get("/document", response_model=DocumentView)
async def document(
    settings: SettingsDep,
    path: Annotated[str, Query(max_length=400, description="Depo kokune gore goreli yol")],
) -> DocumentView:
    """Tek bir dosyanin IR goruntusu ve ham metni."""
    return build_document_view(settings.repo_path, path)
