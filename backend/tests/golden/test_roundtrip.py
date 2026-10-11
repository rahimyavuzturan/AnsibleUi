"""★ ALTIN TESTLER — kayipsiz gidis-donus sozlesmesi.

Bu dosyadaki testlerden biri kirmizi ise HICBIR SEY merge edilmez.
Projenin temel vaadi budur: dokunulmayan hicbir bayt degismez.

Bkz. docs/adr/ADR-0007-surgical-text-patching.md
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest
from app.ansible.roundtrip import (
    TextEdit,
    apply_edits,
    parse_document,
    serialize_document,
)
from app.core.errors import RoundTripError, ValidationError

from tests.golden.conftest import (
    iter_reference_yaml_files,
    reference_id,
    requires_reference_repo,
)

pytestmark = pytest.mark.golden

_REFERENCE_FILES = iter_reference_yaml_files()

# Referans depoda gercekten bozuk olan dosyalar. Bunlar platformun kusuru
# degil, deponun mevcut durumudur; ADR-0007 "Yan Bulgular" bolumune bakin.
KNOWN_BROKEN = {
    "playbooks/PowerFactoreCore/prod-dmz.yml",
    "playbooks/PowerFactoreCore/test-dmz.yml",
    "playbooks/winservices/install_FileBeat.yml",
}


def _read_exact(path: Path) -> str:
    """Dosyayi satir sonlarini DONUSTURMEDEN okur.

    ``Path.read_text`` evrensel satir sonu donusumu yapar ve CRLF'i gizler;
    kayipsizlik testlerinde bu kabul edilemez.
    """
    return path.read_bytes().decode("utf-8")


def _first_difference(left: str, right: str) -> str:
    """Ilk farkli karakterin konumunu ve baglamini aciklar."""
    for index, (a, b) in enumerate(zip(left, right, strict=False)):
        if a != b:
            line = left[:index].count("\n") + 1
            return f"satir {line}, karakter {index}: {a!r} != {b!r}"
    return f"uzunluk farki: {len(left)} != {len(right)}"


# ---------------------------------------------------------------------------
# 1. Gidis-donus: dokunulmamis dosya birebir ayni kalmali
# ---------------------------------------------------------------------------


@requires_reference_repo
@pytest.mark.parametrize("yaml_path", _REFERENCE_FILES, ids=reference_id)
def test_roundtrip_is_byte_identical(yaml_path: Path) -> None:
    """Her YAML dosyasi parse->serialize sonrasi byte duzeyinde ayni kalmalidir."""
    original = yaml_path.read_bytes()
    document = parse_document(original.decode("utf-8"))
    produced = serialize_document(document).encode("utf-8")

    assert produced == original, (
        f"{yaml_path.name} kayipsiz geri yazilamadi: "
        f"{_first_difference(original.decode('utf-8'), produced.decode('utf-8'))}"
    )


# ---------------------------------------------------------------------------
# 2. Ayristirma kapsami
# ---------------------------------------------------------------------------


@requires_reference_repo
@pytest.mark.parametrize("yaml_path", _REFERENCE_FILES, ids=reference_id)
def test_document_is_parsed_or_reported(yaml_path: Path) -> None:
    """Dosya ya ayristirilir ya da bilinen bozuk listesinde olur.

    Sessizce yutulan ayristirma hatasi kabul edilmez: her hata ya duzeltilir
    ya da bilincli olarak KNOWN_BROKEN listesine eklenir.
    """
    from tests.golden.conftest import REFERENCE_REPO

    assert REFERENCE_REPO is not None
    relative = yaml_path.relative_to(REFERENCE_REPO).as_posix()
    document = parse_document(_read_exact(yaml_path))

    if relative in KNOWN_BROKEN:
        assert not document.is_parsed, (
            f"{relative} artik ayristirilabiliyor — KNOWN_BROKEN listesinden cikarin"
        )
        return

    assert document.is_parsed, f"{relative} ayristirilamadi: {document.parse_error}"


@requires_reference_repo
def test_span_coverage_is_complete() -> None:
    """Ayristirilan her dosyada en az bir dugum araligi cikarilmalidir."""
    from tests.golden.conftest import REFERENCE_REPO

    assert REFERENCE_REPO is not None
    empty: list[str] = []
    for yaml_path in _REFERENCE_FILES:
        document = parse_document(_read_exact(yaml_path))
        if not document.is_parsed or document.data is None:
            continue
        if not document.spans:
            empty.append(yaml_path.relative_to(REFERENCE_REPO).as_posix())

    assert empty == [], f"Aralik cikarilamayan dosyalar: {empty}"


@requires_reference_repo
@pytest.mark.parametrize("yaml_path", _REFERENCE_FILES, ids=reference_id)
def test_spans_point_at_valid_ranges(yaml_path: Path) -> None:
    """Her dugum araligi metin sinirlari icinde ve tutarli olmalidir."""
    document = parse_document(_read_exact(yaml_path))
    if not document.is_parsed:
        return  # bilinen bozuk dosyalar test_document_is_parsed_or_reported ile ele alinir

    length = len(document.normalized_text)
    for span in document.spans.values():
        assert 0 <= span.start <= span.end <= length, (
            f"{span.pointer} gecersiz aralik: {span.start}-{span.end} (uzunluk {length})"
        )


# ---------------------------------------------------------------------------
# 3. Yama sozlesmesi: yalnizca hedef degisir
# ---------------------------------------------------------------------------


@pytest.fixture
def isube_freshserver(reference_repo: Path) -> Path:
    """Gercek, buyuk ve karma girintili bir gorev dosyasi."""
    path = (
        reference_repo
        / "roles_custom"
        / "install_isube"
        / "tasks"
        / "install_isube_nonprod_freshserver.yml"
    )
    if not path.is_file():
        pytest.skip("ornek dosya referans depoda bulunamadi")
    return path


@requires_reference_repo
def test_patch_only_touches_target(isube_freshserver: Path) -> None:
    """Hedefli yama, dokunulmayan satirlari degistirmemelidir."""
    original = _read_exact(isube_freshserver)
    document = parse_document(original)

    span = document.span("/0/vars/paths/0")
    edit = TextEdit(span.start, span.end, "'D:\\WebSitesYeni'", reason="test")
    produced = serialize_document(document, [edit])

    diff = list(
        difflib.unified_diff(
            original.splitlines(),
            produced.splitlines(),
            lineterm="",
            n=0,
        )
    )
    added = [line for line in diff if line.startswith("+") and not line.startswith("+++")]
    removed = [line for line in diff if line.startswith("-") and not line.startswith("---")]

    assert len(added) == 1, f"beklenmeyen eklemeler: {added}"
    assert len(removed) == 1, f"beklenmeyen silmeler: {removed}"
    assert "D:\\WebSitesYeni" in added[0]


@requires_reference_repo
def test_patch_preserves_line_endings(isube_freshserver: Path) -> None:
    """Yama sonrasi satir sonu stili degismemelidir."""
    original = _read_exact(isube_freshserver)
    document = parse_document(original)

    span = document.span("/0/vars/paths/0")
    produced = serialize_document(
        document, [TextEdit(span.start, span.end, "'D:\\Yeni'", reason="test")]
    )

    assert produced.count("\r\n") == original.count("\r\n")
    assert produced.count("\n") == original.count("\n")


@requires_reference_repo
def test_unmodified_document_returns_identical_text(isube_freshserver: Path) -> None:
    """Yama verilmediginde cikti girdinin birebir aynisidir."""
    original = _read_exact(isube_freshserver)
    document = parse_document(original)
    assert serialize_document(document) == original
    assert serialize_document(document, []) == original


@requires_reference_repo
def test_no_task_is_lost(isube_freshserver: Path) -> None:
    """Dosyadaki her ust duzey gorev bir aralikla temsil edilmelidir."""
    document = parse_document(_read_exact(isube_freshserver))
    assert document.is_parsed

    top_level = [
        pointer for pointer in document.spans if pointer.count("/") == 1 and pointer[1:].isdigit()
    ]
    assert len(top_level) == len(document.data)
    assert len(top_level) > 0


# ---------------------------------------------------------------------------
# 4. Yama motorunun guvenlik kurallari
# ---------------------------------------------------------------------------


def test_overlapping_edits_are_rejected() -> None:
    """Cakisan yamalar sessizce birlesmez, hata verir."""
    with pytest.raises(ValidationError):
        apply_edits("abcdef", [TextEdit(0, 4, "X"), TextEdit(2, 6, "Y")])


def test_edits_outside_text_are_rejected() -> None:
    """Metin sinirlarini asan yama reddedilir."""
    with pytest.raises(ValidationError):
        apply_edits("abc", [TextEdit(1, 99, "X")])


def test_multiple_edits_apply_in_correct_order() -> None:
    """Birden fazla yama birbirinin indeksini kaydirmamalidir."""
    result = apply_edits(
        "aaa bbb ccc",
        [TextEdit(8, 11, "ZZZZZ"), TextEdit(0, 3, "X")],
    )
    assert result == "X bbb ZZZZZ"


def test_patch_producing_invalid_yaml_is_rejected() -> None:
    """Yama sonrasi dosya bozuluyorsa yazma iptal edilir."""
    document = parse_document("- name: test\n  value: 1\n")
    span = document.span("/0/value")
    with pytest.raises(RoundTripError):
        serialize_document(document, [TextEdit(span.start, span.end, "'unterminated")])


def test_unparseable_document_cannot_be_edited() -> None:
    """Ayristirilamayan dosya salt-okunurdur."""
    document = parse_document("key: value:\n  broken: [\n")
    assert not document.is_parsed
    with pytest.raises(RoundTripError):
        serialize_document(document, [TextEdit(0, 1, "x")])
