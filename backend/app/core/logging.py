"""Yapilandirilmis JSON loglama.

Log kayitlarina gizli bilgi sizmasini onlemek icin bir maskeleme islemcisi
zincire eklenir. Bu islemci kaldirilmamalidir.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

# Log ciktisinda maskelenmesi gereken anahtar adlari.
_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pass",
        "secret",
        "token",
        "pat",
        "authorization",
        "api_key",
        "apikey",
        "jwt",
        "cookie",
        "set-cookie",
        "vault_password",
        "cert_password",
        "certpassword",
    }
)

# Deger icinde gecen token benzeri desenler (PAT, Bearer, Basic).
_SENSITIVE_VALUE_PATTERN = re.compile(
    r"(Bearer\s+|Basic\s+)[A-Za-z0-9+/=._-]{8,}",
    re.IGNORECASE,
)

_MASK = "***"


def _mask_value(value: Any) -> Any:
    """Bir degeri, ic ice yapilari da gezerek maskeler."""
    if isinstance(value, str):
        return _SENSITIVE_VALUE_PATTERN.sub(lambda m: f"{m.group(1)}{_MASK}", value)
    if isinstance(value, dict):
        return {k: (_MASK if _is_sensitive(k) else _mask_value(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_value(item) for item in value]
    return value


def _is_sensitive(key: Any) -> bool:
    return isinstance(key, str) and key.lower() in _SENSITIVE_KEYS


def mask_secrets(
    _logger: Any, _method_name: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Structlog islemcisi: gizli alanlari maskeler.

    Bu islemci zincirden cikarilirsa PAT ve parolalar loglara dusebilir.
    """
    return {k: (_MASK if _is_sensitive(k) else _mask_value(v)) for k, v in event_dict.items()}


def configure_logging(level: str = "INFO", *, json_output: bool = True) -> None:
    """Structlog ve standart kutuphane loglamasini yapilandirir."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            mask_secrets,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Modul adiyla bagli bir logger dondurur."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
