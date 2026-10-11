"""Depo yolu guvenligi testleri.

Bu testler path traversal savunmasini dogrular. Basarisiz olmalari, depo
disina yazma acigi anlamina gelir; bu yuzden gevsetilmemelidir.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.errors import UnsafePathError
from app.core.paths import normalize_repo_path, resolve_within_repo, to_repo_relative


@pytest.mark.parametrize(
    "raw",
    [
        "playbooks/tsube/install_tsube.yml",
        "roles/create_dir/tasks/main.yml",
        "roles_custom/install_isube/tasks/main.yml",
        "inventory/z_altortam_all",
        "azure-pipelines/nonprod/azure-pipelines-playbook.yml",
        "group_vars/certStoreVar/certStorePublic.yml",
        "templates/mailTemplate.html.j2",
    ],
)
def test_izinli_yollar_kabul_edilir(raw: str) -> None:
    assert str(normalize_repo_path(raw)) == raw


def test_ters_bolu_normallestirilir() -> None:
    assert (
        str(normalize_repo_path("playbooks\\tsube\\install.yml")) == "playbooks/tsube/install.yml"
    )


@pytest.mark.parametrize(
    "raw",
    [
        "../etc/passwd",
        "playbooks/../../secret.yml",
        "playbooks/../.git/config",
        "roles/../../../../etc/shadow",
    ],
)
def test_ust_dizine_cikis_reddedilir(raw: str) -> None:
    with pytest.raises(UnsafePathError):
        normalize_repo_path(raw)


@pytest.mark.parametrize(
    "raw",
    ["/etc/passwd", "C:\\Windows\\System32\\config", "D:/gizli/dosya.yml"],
)
def test_mutlak_yol_reddedilir(raw: str) -> None:
    with pytest.raises(UnsafePathError):
        normalize_repo_path(raw)


@pytest.mark.parametrize(
    "raw",
    [
        ".git/config",
        "scripts/addVaultPass.sh",
        "README.md",
        "files/others/secret.pfx",
    ],
)
def test_izinli_olmayan_kok_reddedilir(raw: str) -> None:
    """Yalnizca ALLOWED_ROOTS altindaki klasorler duzenlenebilir."""
    with pytest.raises(UnsafePathError):
        normalize_repo_path(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "playbooks/a b/c.yml",
        "playbooks/tsube/install;rm -rf.yml",
        "playbooks/$(whoami)/x.yml",
        "playbooks/tsube/install`id`.yml",
        "playbooks/tsube/x|y.yml",
    ],
)
def test_zararli_karakterler_reddedilir(raw: str) -> None:
    with pytest.raises(UnsafePathError):
        normalize_repo_path(raw)


@pytest.mark.parametrize("raw", ["", "   ", "."])
def test_bos_yol_reddedilir(raw: str) -> None:
    with pytest.raises(UnsafePathError):
        normalize_repo_path(raw)


def test_resolve_within_repo_mutlak_yol_uretir(tmp_repo: Path) -> None:
    hedef = resolve_within_repo(tmp_repo, "playbooks/test.yml")
    assert hedef == (tmp_repo / "playbooks" / "test.yml").resolve()
    assert hedef.is_relative_to(tmp_repo.resolve())


def test_resolve_within_repo_kacisi_engeller(tmp_repo: Path) -> None:
    with pytest.raises(UnsafePathError):
        resolve_within_repo(tmp_repo, "playbooks/../../disari.yml")


def test_to_repo_relative(tmp_repo: Path) -> None:
    mutlak = tmp_repo / "roles" / "create_dir" / "tasks" / "main.yml"
    mutlak.parent.mkdir(parents=True, exist_ok=True)
    mutlak.touch()
    assert str(to_repo_relative(tmp_repo, mutlak)) == "roles/create_dir/tasks/main.yml"


def test_to_repo_relative_disaridaki_yolu_reddeder(tmp_repo: Path, tmp_path: Path) -> None:
    disarisi = tmp_path / "baska" / "dosya.yml"
    disarisi.parent.mkdir(parents=True, exist_ok=True)
    disarisi.touch()
    with pytest.raises(UnsafePathError):
        to_repo_relative(tmp_repo, disarisi)
