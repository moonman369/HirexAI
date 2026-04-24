import logging

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

from app.api.router import api_router

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title="HirexAI API",
    description=(
        "AI-assisted hiring workflow API for scraping job descriptions, "
        "matching candidate fit, and managing referral outreach."
    ),
    version="0.1.0",
    docs_url="/swagger",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.include_router(api_router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/swagger")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
