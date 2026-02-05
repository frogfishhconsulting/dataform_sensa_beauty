from __future__ import annotations

import logging

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import engine


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    log = logging.getLogger("app")
    app = FastAPI(title="Zeitgeist → RSA Agent", version="0.1.0")
    app.include_router(api_router)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.on_event("startup")
    def on_startup() -> None:
        if settings.db_auto_create:
            log.info("db_auto_create enabled; creating tables if needed")
            Base.metadata.create_all(bind=engine)

    return app


app = create_app()

