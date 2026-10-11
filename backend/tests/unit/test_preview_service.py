"""Onizleme uclarinin birim testleri.

Onizleme gecici olsa da iki sey kalicidir: depo icerigi bozulmamali ve
yol dogrulamasi (path traversal) delinmemelidir.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.services.preview_service import (
    RepoMissingError,
    build_document_view,
    scan_repository,
)
from app.core.errors import UnsafePathError

PLAYBOOK = (
    "---\n"
    "- name: test oynatma\n"
    "  hosts: web\n"
    "  roles:\n"
    "    - role: create_dir\n"
    "      paths:\n"
    "        - D:\\WebSites\\App\n"
    "  tasks:\n"
    "    - name: bilgi\n"
    "      debug:\n"
    "        msg: merhaba\n"
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    target = tmp_path / "playbooks" / "demo"
    target.mkdir(parents=True)
    (target / "install.yml").write_text(PLAYBOOK, encoding="utf-8")
    return tmp_path


def test_depo_taramasi_dosyalari_ve_dugumleri_sayar(repo: Path) -> None:
    summary = scan_repository(repo)
    assert summary.file_count == 1
    assert summary.role_call_count == 1
    assert summary.kind_counts["playbook"] == 1
    assert summary.top_roles[0]["name"] == "create_dir"


def test_belge_goruntusu_kaynagi_aynen_dondurur(repo: Path) -> None:
    """Onizleme metni degistirmemelidir; ekranda gosterilen birebir kaynaktir."""
    view = build_document_view(repo, "playbooks/demo/install.yml")
    assert view.text == PLAYBOOK
    assert view.editable
    assert view.nodes[0].type == "play"


def test_dugum_satir_araligi_kaynakla_ortusur(repo: Path) -> None:
    view = build_document_view(repo, "playbooks/demo/install.yml")
    role = view.nodes[0].children[0]
    lines = PLAYBOOK.split("\n")
    assert "role: create_dir" in lines[role.line_start - 1]


def test_depo_disina_cikan_yol_reddedilir(repo: Path) -> None:
    with pytest.raises(UnsafePathError):
        build_document_view(repo, "../../../etc/passwd")


def test_izin_verilmeyen_kok_reddedilir(repo: Path) -> None:
    with pytest.raises(UnsafePathError):
        build_document_view(repo, ".git/config")


def test_depo_yoksa_anlasilir_hata_verir(tmp_path: Path) -> None:
    with pytest.raises(RepoMissingError):
        scan_repository(tmp_path / "yok")
