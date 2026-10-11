"""Kayipsiz YAML modulunun birim testleri.

Altin testler gercek depoya bakar; bu testler kenar durumlari kapsar.
"""

from __future__ import annotations

import pytest
from app.ansible.roundtrip import (
    TextEdit,
    apply_edits,
    parse_document,
    render_scalar,
    serialize_document,
)
from app.core.errors import RoundTripError, ValidationError

# ---------------------------------------------------------------------------
# Bicim korunmasi
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "",
        "---\n",
        "# yalnizca yorum\n",
        "- name: tek gorev\n",
        "- name: son satir sonu yok",
        "key: value\n\n\n",
        "\ufeff- name: bom ile\n",
        "- name: crlf\r\n  state: present\r\n",
    ],
)
def test_degisiklik_yoksa_metin_aynen_doner(text: str) -> None:
    assert serialize_document(parse_document(text)) == text


def test_crlf_tespit_edilir() -> None:
    document = parse_document("a: 1\r\nb: 2\r\n")
    assert document.newline == "\r\n"
    assert "\r" not in document.normalized_text


def test_lf_tespit_edilir() -> None:
    document = parse_document("a: 1\nb: 2\n")
    assert document.newline == "\n"


def test_bom_tespit_edilir_ve_geri_yazilir() -> None:
    document = parse_document("\ufeffa: 1\n")
    assert document.has_bom
    assert not document.normalized_text.startswith("\ufeff")

    span = document.span("/a")
    assert serialize_document(document, [TextEdit(span.start, span.end, "2")]).startswith("\ufeff")


def test_crlf_yama_sonrasi_korunur() -> None:
    document = parse_document("a: 1\r\nb: 2\r\n")
    span = document.span("/a")
    produced = serialize_document(document, [TextEdit(span.start, span.end, "99")])
    assert produced == "a: 99\r\nb: 2\r\n"


# ---------------------------------------------------------------------------
# Aralik (span) tespiti
# ---------------------------------------------------------------------------


def test_skaler_araligi_tirnaklari_icerir() -> None:
    document = parse_document("a: 'tirnakli'\n")
    assert document.text_at("/a") == "'tirnakli'"
    assert document.span("/a").style == "'"


def test_ic_ice_yapilarda_pointer_uretilir() -> None:
    document = parse_document("- vars:\n    paths:\n      - bir\n      - iki\n")
    assert document.text_at("/0/vars/paths/1") == "iki"
    assert document.span("/0/vars/paths").kind == "sequence"
    assert document.span("/0").kind == "mapping"


def test_egik_cizgi_iceren_anahtar_kacirilir() -> None:
    document = parse_document("a/b: 1\n")
    assert document.text_at("/a~1b") == "1"


def test_bilinmeyen_pointer_hata_verir() -> None:
    document = parse_document("a: 1\n")
    with pytest.raises(ValidationError):
        document.span("/yok")


def test_bos_belge_arilik_icermez() -> None:
    document = parse_document("# sadece yorum\n")
    assert document.is_parsed
    assert document.spans == {}


# ---------------------------------------------------------------------------
# Ayristirma hatalari
# ---------------------------------------------------------------------------


def test_bozuk_yaml_istisna_firlatmaz() -> None:
    """Bozuk dosya platformun calismasini durdurmamalidir."""
    document = parse_document("a: b: c\n")
    assert not document.is_parsed
    assert document.parse_error is not None
    assert "ScannerError" in document.parse_error or "ParserError" in document.parse_error


def test_tanimsiz_alias_ayristirilamaz() -> None:
    document = parse_document("a: *yok\n")
    assert not document.is_parsed


def test_bozuk_dosya_metni_korunur() -> None:
    """Ayristirilamasa bile orijinal metin kaybolmaz."""
    text = "a: b: c\n"
    assert serialize_document(parse_document(text)) == text


# ---------------------------------------------------------------------------
# Yama motoru
# ---------------------------------------------------------------------------


def test_bos_yama_listesi_metni_degistirmez() -> None:
    assert apply_edits("abc", []) == "abc"


def test_yama_ekleme_yapabilir() -> None:
    assert apply_edits("ac", [TextEdit(1, 1, "b")]) == "abc"


def test_yama_silme_yapabilir() -> None:
    assert apply_edits("abc", [TextEdit(1, 2, "")]) == "ac"


def test_bitisik_yamalar_kabul_edilir() -> None:
    assert apply_edits("abcd", [TextEdit(0, 2, "X"), TextEdit(2, 4, "Y")]) == "XY"


def test_negatif_aralik_reddedilir() -> None:
    with pytest.raises(ValidationError):
        TextEdit(5, 2, "x")


def test_sirasiz_yamalar_dogru_uygulanir() -> None:
    result = apply_edits("111 222 333", [TextEdit(8, 11, "C"), TextEdit(0, 3, "A")])
    assert result == "A 222 C"


def test_yama_sonrasi_gecersiz_yaml_reddedilir() -> None:
    document = parse_document("- a: 1\n")
    span = document.span("/0/a")
    with pytest.raises(RoundTripError):
        serialize_document(document, [TextEdit(span.start, span.end, "[bozuk")])


# ---------------------------------------------------------------------------
# Deger uretimi
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (42, "42"),
        (True, "true"),
        ("basit", "basit"),
        ("iki: nokta", "'iki: nokta'"),
        ("# diye baslayan", "'# diye baslayan'"),
        ("", "''"),
    ],
)
def test_skaler_uretimi_kacirma_yapar(value: object, expected: str) -> None:
    assert render_scalar(value) == expected


def test_skaler_uretimi_tirnak_stili_zorlanabilir() -> None:
    assert render_scalar("deger", style="'") == "'deger'"


def test_uretilen_skaler_yamada_kullanilabilir() -> None:
    """Uretilen deger dosyaya yazildiginda gecerli YAML olusturmalidir."""
    document = parse_document("- ad: eski\n")
    span = document.span("/0/ad")
    produced = serialize_document(
        document, [TextEdit(span.start, span.end, render_scalar("yeni: deger"))]
    )
    assert produced == "- ad: 'yeni: deger'\n"
    assert parse_document(produced).is_parsed
