from __future__ import annotations

from fastapi import FastAPI

from app.config import settings
from app.db.mongo import init_indexes
from app.routes.auth import router as auth_router
from app.routes.jobs import router as jobs_router
from app.routes.profile import router as profile_router


app = FastAPI(title=settings.app_name, version="1.0.0")


@app.on_event("startup")
def startup_event() -> None:
    init_indexes()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(jobs_router)
