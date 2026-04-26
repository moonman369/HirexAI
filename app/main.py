from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.config import settings
from app.db.mongo import init_indexes
from app.routes.auth import router as auth_router
from app.routes.jobs import router as jobs_router
from app.routes.profile import router as profile_router


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    swagger_ui_parameters={"persistAuthorization": True},
)


@app.on_event("startup")
def startup_event() -> None:
    init_indexes()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    components = openapi_schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes.setdefault(
        "BearerAuth",
        {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Paste access token (without Bearer prefix).",
        },
    )
    openapi_schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(jobs_router)
