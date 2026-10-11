"""Depo icindeki dosya yollarinin guvenli sekilde ele alinmasi.

Kullanicidan gelen her yol bu modulden gecmelidir. Amac, path traversal
(OWASP A01) saldirilarini ve depo disina yazmayi engellemektir.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from app.core.errors import UnsafePathError

# Duzenlenmesine izin verilen ust klasorler. Bu listenin disindaki hicbir yol
# okunamaz veya yazilamaz. Ozellikle .git ve azure-pipelines disi kok dosyalar
# bilincli olarak disaridadir.
ALLOWED_ROOTS: tuple[str, ...] = (
    "playbooks",
    "roles",
    "roles_custom",
    "inventory",
    "group_vars",
    "host_vars",
    "templates",
    "azure-pipelines",
)

# Yol bileseninde izin verilen karakterler. Bos olmayan, gizli olmayan,
# kabuk acisindan zararsiz adlar.
_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def normalize_repo_path(raw: str) -> PurePosixPath:
    """Kullanicidan gelen depo-ici yolu dogrular ve normallestirir.

    Args:
        raw: Depo kokune gore goreli yol. Ornegin ``playbooks/tsube/install.yml``.

    Returns:
        Normallestirilmis POSIX yolu.

    Raises:
        UnsafePathError: Yol mutlaksa, depo disina cikiyorsa, izinli kok
            klasorlerden birinde degilse veya gecersiz karakter iceriyorsa.
    """
    if not raw or not raw.strip():
        raise UnsafePathError("Dosya yolu bos olamaz")

    candidate = raw.strip().replace("\\", "/")

    if candidate.startswith("/") or re.match(r"^[A-Za-z]:", candidate):
        raise UnsafePathError("Mutlak yol kabul edilmez", details={"path": raw})

    parts = [p for p in PurePosixPath(candidate).parts if p not in (".", "")]

    if not parts:
        raise UnsafePathError("Gecersiz dosya yolu", details={"path": raw})

    for part in parts:
        if part == "..":
            raise UnsafePathError("Ust dizine cikilamaz", details={"path": raw})
        if not _SEGMENT_PATTERN.match(part):
            raise UnsafePathError(
                "Dosya yolu gecersiz karakter iceriyor",
                details={"path": raw, "segment": part},
            )

    if parts[0] not in ALLOWED_ROOTS:
        raise UnsafePathError(
            "Bu klasor duzenlemeye acik degil",
            details={"path": raw, "allowed": list(ALLOWED_ROOTS)},
        )

    return PurePosixPath(*parts)


def resolve_within_repo(repo_root: Path, raw: str) -> Path:
    """Depo-ici goreli yolu mutlak yola cevirir ve kok icinde kaldigini dogrular.

    Sembolik baglantilarla depo disina cikilmasini da engeller.

    Args:
        repo_root: Git calisma kopyasinin kok dizini.
        raw: Depo kokune gore goreli yol.

    Returns:
        Depo kokunun altinda kaldigi dogrulanmis mutlak yol.

    Raises:
        UnsafePathError: Cozumlenen yol depo kokunun disina cikiyorsa.
    """
    relative = normalize_repo_path(raw)
    root = repo_root.resolve()
    resolved = (root / Path(*relative.parts)).resolve()

    if not resolved.is_relative_to(root):
        raise UnsafePathError("Yol depo kokunun disina cikiyor", details={"path": raw})

    return resolved


def to_repo_relative(repo_root: Path, absolute: Path) -> PurePosixPath:
    """Mutlak bir yolu depo kokune gore goreli POSIX yoluna cevirir."""
    root = repo_root.resolve()
    resolved = absolute.resolve()
    if not resolved.is_relative_to(root):
        raise UnsafePathError("Yol depo kokunun disinda", details={"path": str(absolute)})
    return PurePosixPath(*resolved.relative_to(root).parts)
