from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.runs import router as runs_router

api_router = APIRouter(prefix="/api")
api_router.include_router(runs_router, prefix="/runs", tags=["runs"])

