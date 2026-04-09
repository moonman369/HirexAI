"""Runtime wiring helpers for constructing the MVP processing pipeline."""

from __future__ import annotations

import os

from app.services.decision_service import DecisionService
from app.services.matcher_service import MatcherService
from app.services.openai_clients import OpenAIEmbeddingClient, OpenAIOutreachClient, OpenAIReasoningClient
from app.services.outreach_service import OutreachService
from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.services.scraper_service import ScraperService


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def validate_runtime_configuration() -> None:
    """Validate required runtime environment variables with clear failures."""
    _required_env("MONGO_URI")
    _required_env("MONGO_DB")
    _required_env("OPENAI_API_KEY")


def build_pipeline_orchestrator() -> PipelineOrchestrator:
    """Construct a pipeline orchestrator with concrete service dependencies."""
    api_key = _required_env("OPENAI_API_KEY")

    scraper_service = ScraperService()
    matcher_service = MatcherService(
        embedding_client=OpenAIEmbeddingClient(api_key=api_key),
        reasoning_client=OpenAIReasoningClient(api_key=api_key),
    )
    outreach_service = OutreachService(generator_client=OpenAIOutreachClient(api_key=api_key))
    decision_service = DecisionService(threshold=0.75)

    return PipelineOrchestrator(
        scraper=scraper_service,
        matcher=matcher_service,
        outreach_generator=outreach_service,
        decision_service=decision_service,
    )
