"""Altin testler icin ortak duzenekler.

Referans depo (``Ansible.appAdminConfig``) bu testlerin veri kaynagidir.
Depo bulunamazsa yerel gelistirmede testler atlanir; CI'da ise
``ANSIBLEUI_GOLDEN_REQUIRED=1`` ile atlama YASAKLANIR.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_ENV_REPO = "ANSIBLEUI_REFERENCE_REPO"
_ENV_REQUIRED = "ANSIBLEUI_GOLDEN_REQUIRED"


def _candidate_roots() -> list[Path]:
    """Referans deponun aranacagi yerler."""
    explicit = os.environ.get(_ENV_REPO)
    roots = [Path(explicit)] if explicit else []
    # backend/tests/golden -> backend/tests -> backend -> ansible-ui -> calisma alani
    workspace = Path(__file__).resolve().parents[4]
    roots.append(workspace / "Ansible.appAdminConfig")
    return roots


def find_reference_repo() -> Path | None:
    """Referans deponun kok dizinini bulur; yoksa ``None``."""
    for root in _candidate_roots():
        if (root / "roles").is_dir() and (root / "playbooks").is_dir():
            return root
    return None


REFERENCE_REPO = find_reference_repo()

if REFERENCE_REPO is None and os.environ.get(_ENV_REQUIRED) == "1":
    raise RuntimeError(
        "Referans depo bulunamadi ve altin testler zorunlu isaretlenmis. "
        f"{_ENV_REPO} degiskenini ayarlayin."
    )

requires_reference_repo = pytest.mark.skipif(
    REFERENCE_REPO is None,
    reason="Referans depo bulunamadi (ANSIBLEUI_REFERENCE_REPO ile yol verilebilir)",
)


def iter_reference_yaml_files() -> list[Path]:
    """Referans depodaki tum YAML dosyalarini dondurur."""
    if REFERENCE_REPO is None:
        return []
    files = [
        path
        for pattern in ("*.yml", "*.yaml")
        for path in REFERENCE_REPO.rglob(pattern)
        if ".git" not in path.parts
    ]
    return sorted(files)


def reference_id(path: Path) -> str:
    """Test kimligi icin depoya gore goreli yol."""
    if REFERENCE_REPO is None:
        return path.name
    return path.relative_to(REFERENCE_REPO).as_posix()


@pytest.fixture(scope="session")
def reference_repo() -> Path:
    """Referans deponun kok dizini."""
    if REFERENCE_REPO is None:
        pytest.skip("Referans depo bulunamadi")
    return REFERENCE_REPO
