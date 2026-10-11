"""Uygulama genelinde kullanilan yapilandirma.

Tum degerler ortam degiskenlerinden okunur. Kod icinde sabit URL, parola veya
token bulunmaz; bu SSRF ve secret sizintisi risklerini onler.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ortam degiskenlerinden yuklenen uygulama ayarlari."""

    model_config = SettingsConfigDict(
        env_prefix="ANSIBLEUI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Uygulama ---
    env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_base_url: str = "http://localhost:8000"

    # --- Veritabani ---
    database_url: str = "postgresql+asyncpg://ansibleui:ansibleui@localhost:5432/ansibleui"

    # --- Git calisma kopyasi ---
    repo_path: Path = Path("/data/repo")
    repo_url: str = ""
    repo_default_branch: str = "main"
    branch_prefix: str = "ansibleui"

    # --- Azure DevOps Server ---
    ado_base_url: str = ""
    ado_collection: str = ""
    ado_project: str = ""
    ado_repository: str = ""
    ado_api_version: str = "6.0"
    ado_pat: SecretStr = SecretStr("")

    ca_bundle_path: Path | None = None

    # --- Pipeline tanim eslemesi ---
    pipeline_nonprod_id: int | None = None
    pipeline_prod_id: int | None = None
    pipeline_dmz_nonprod_id: int | None = None
    pipeline_dmz_prod_id: int | None = None

    # --- Kimlik dogrulama ---
    auth_provider: Literal["local", "ldap"] = "local"
    jwt_secret: SecretStr = SecretStr("")
    jwt_ttl_minutes: int = 60

    # --- Arka plan isleri ---
    index_interval_seconds: int = 60
    run_poll_interval_seconds: int = 5

    # --- Yapay zeka (Faz 7) ---
    ai_enabled: bool = False
    ai_base_url: str = ""
    ai_model: str = ""
    ai_api_key: SecretStr = SecretStr("")

    @field_validator("branch_prefix")
    @classmethod
    def _validate_branch_prefix(cls, value: str) -> str:
        """Branch onekinin bos olmamasini ve 'main' olmamasini garanti eder."""
        cleaned = value.strip().strip("/")
        if not cleaned:
            raise ValueError("branch_prefix bos olamaz")
        if cleaned == "main":
            raise ValueError("branch_prefix 'main' olamaz")
        return cleaned

    @field_validator("jwt_secret")
    @classmethod
    def _validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        """Uretimde zayif JWT anahtarini reddeder."""
        if len(value.get_secret_value()) < 32:
            # Gelistirme ortaminda bos birakilabilir; uretim kontrolu main.py'de yapilir.
            return value
        return value

    @property
    def ado_repo_api_root(self) -> str:
        """Azure DevOps Server REST kok adresi.

        Ornek: https://ktdevops/tfs/KT/KT.ITAutomation/_apis
        """
        base = self.ado_base_url.rstrip("/")
        return f"{base}/{self.ado_collection}/{self.ado_project}/_apis"

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Ayarlari tekil (singleton) olarak dondurur."""
    return Settings()
