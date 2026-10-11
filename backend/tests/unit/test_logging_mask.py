"""Log maskeleme testleri.

Gizli bilgilerin loglara dusmemesi guvenlik gerekliligidir.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import mask_secrets


def _mask(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(mask_secrets(None, "info", payload))


def test_hassas_anahtarlar_maskelenir() -> None:
    sonuc = _mask({"event": "giris", "password": "gizli123", "token": "abcdef"})
    assert sonuc["password"] == "***"
    assert sonuc["token"] == "***"
    assert sonuc["event"] == "giris"


def test_ic_ice_sozlukte_maskelenir() -> None:
    sonuc = _mask({"istek": {"headers": {"Authorization": "Bearer xyz", "Accept": "json"}}})
    assert sonuc["istek"]["headers"]["Authorization"] == "***"
    assert sonuc["istek"]["headers"]["Accept"] == "json"


def test_liste_icindeki_sozlukler_maskelenir() -> None:
    sonuc = _mask({"kayitlar": [{"pat": "abc123"}, {"ad": "test"}]})
    assert sonuc["kayitlar"][0]["pat"] == "***"
    assert sonuc["kayitlar"][1]["ad"] == "test"


def test_deger_icindeki_bearer_token_maskelenir() -> None:
    sonuc = _mask({"mesaj": "istek basligi: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6"})
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6" not in sonuc["mesaj"]
    assert "***" in sonuc["mesaj"]


def test_zararsiz_veriler_degismez() -> None:
    girdi = {"event": "indeks_guncellendi", "dosya_sayisi": 120, "branch": "main"}
    assert _mask(girdi) == girdi
