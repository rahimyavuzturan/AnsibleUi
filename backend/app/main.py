"""FastAPI uygulama giris noktasi."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.preview import router as preview_router
from app.core.config import Settings, get_settings
from app.core.errors import AnsibleUIError
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)

WEB_DIR = Path(__file__).parent / "web"


def _assert_production_ready(settings: Settings) -> None:
    """Uretim ortaminda zayif yapilandirmayla acilmayi engeller."""
    if not settings.is_production:
        return

    problems: list[str] = []
    if len(settings.jwt_secret.get_secret_value()) < 32:
        problems.append("ANSIBLEUI_JWT_SECRET en az 32 karakter olmali")
    if not settings.ado_pat.get_secret_value():
        problems.append("ANSIBLEUI_ADO_PAT tanimli olmali")
    if not settings.repo_url:
        problems.append("ANSIBLEUI_REPO_URL tanimli olmali")

    if problems:
        raise RuntimeError("Uretim yapilandirmasi eksik: " + "; ".join(problems))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Uygulama yasam dongusu: baslangic ve kapanis islemleri."""
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.is_production)
    _assert_production_ready(settings)
    logger.info("uygulama_basladi", env=settings.env)
    yield
    logger.info("uygulama_kapandi")


def create_app() -> FastAPI:
    """Uygulama nesnesini olusturur ve yapilandirir."""
    settings = get_settings()

    app = FastAPI(
        title="AnsibleUI API",
        description="Ansible deposu icin gorsel otomasyon platformu",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Gelistirmede Vite sunucusuna izin verilir. Uretimde arayuz ayni
    # kok adresten sunuldugu icin capraz kaynak istegi beklenmez.
    if not settings.is_production:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(AnsibleUIError)
    async def _handle_app_error(_request: Request, exc: AnsibleUIError) -> JSONResponse:
        """Uygulama hatalarini tutarli bir JSON formatina cevirir."""
        logger.warning("uygulama_hatasi", code=exc.code, message=exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    app.include_router(health_router)

    # Teknik onizleme: yoneticiye gosterilebilir, Node gerektirmeyen arayuz.
    # Kalici arayuz React ile gelecek (WP-40+). Uretimde bilincli olarak kapali:
    # kimlik dogrulamasi yoktur ve depo icerigini dogrudan sunar.
    if not settings.is_production and WEB_DIR.is_dir():
        app.include_router(preview_router)
        app.mount("/ui", StaticFiles(directory=WEB_DIR, html=True), name="ui")

        @app.get("/", include_in_schema=False)
        async def _root() -> FileResponse:
            """Kok adresi onizleme arayuzune yonlendirir."""
            return FileResponse(WEB_DIR / "index.html")

    return app


app = create_app()
