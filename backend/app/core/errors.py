"""Uygulama geneli hata tipleri.

Tum servis katmani hatalari bu siniflardan turer. API katmani bunlari
HTTP yanitlarina cevirir; boylece ic detaylar istemciye sizmaz.
"""

from __future__ import annotations

from typing import Any


class AnsibleUIError(Exception):
    """Tum uygulama hatalarinin atasi."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AnsibleUIError):
    """Istenen kaynak bulunamadi."""

    status_code = 404
    code = "not_found"


class ValidationError(AnsibleUIError):
    """Girdi dogrulamasi basarisiz."""

    status_code = 422
    code = "validation_error"


class ConflictError(AnsibleUIError):
    """Kaynak durumu istemcinin varsaydigindan farkli (ornegin eskimis taslak)."""

    status_code = 409
    code = "conflict"


class PermissionDeniedError(AnsibleUIError):
    """Kullanicinin bu islem icin yetkisi yok."""

    status_code = 403
    code = "permission_denied"


class AuthenticationError(AnsibleUIError):
    """Kimlik dogrulanamadi."""

    status_code = 401
    code = "unauthenticated"


class UnsafePathError(AnsibleUIError):
    """Depo disina cikmaya calisan veya izin verilmeyen bir dosya yolu."""

    status_code = 400
    code = "unsafe_path"


class RoundTripError(AnsibleUIError):
    """YAML gidis-donusunde veri kaybi tespit edildi.

    Bu hata olumcul kabul edilir: bozuk bir dosya yazmaktansa islem iptal edilir.
    """

    status_code = 500
    code = "roundtrip_failed"


class GitSafetyError(AnsibleUIError):
    """Yasakli bir git islemi denendi (ornegin korumali branch'e yazma)."""

    status_code = 400
    code = "git_safety"


class UpstreamError(AnsibleUIError):
    """Azure DevOps gibi dis bir sistem beklenmeyen yanit dondu."""

    status_code = 502
    code = "upstream_error"
