"""Test ortami icin ortak fixture'lar."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Ayarlar yuklenmeden once test ortami isaretlenir.
os.environ.setdefault("ANSIBLEUI_ENV", "test")
os.environ.setdefault("ANSIBLEUI_JWT_SECRET", "test-secret-key-that-is-long-enough-32")


@pytest.fixture(scope="session")
def reference_repo_path() -> Path:
    """Referans Ansible deposunun kok dizini.

    Bu depo SALT OKUNUR bir referanstir; testler asla icine yazmaz.
    Depo yoksa bagimli testler atlanir.
    """
    candidate = Path(__file__).resolve().parents[3] / "Ansible.appAdminConfig"
    if not candidate.is_dir():
        pytest.skip(f"Referans Ansible deposu bulunamadi: {candidate}")
    return candidate


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Iterator[Path]:
    """Yazilabilir, gecici bir depo koku."""
    root = tmp_path / "repo"
    for folder in ("playbooks", "roles", "roles_custom", "inventory"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    yield root
