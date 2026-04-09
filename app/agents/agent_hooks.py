"""Optional lightweight hooks for agent/tool orchestration."""

from __future__ import annotations

from typing import Any

from app.services.decision_service import DecisionService
from app.services.matcher_service import MatcherService
from app.services.outreach_service import OutreachService
from app.services.scraper_service import ScraperService


def run_scrape_hook(
    *,
    scraper_service: ScraperService,
    job_id: str,
    user_id: str,
    url: str,
) -> dict[str, Any]:
    """Run scrape step as a tool-friendly hook."""
    scrape_result = scraper_service.scrape_with_raw_html(job_id=job_id, user_id=user_id, url=url)
    return {
        "job_id": job_id,
        "user_id": user_id,
        "url": url,
        "jd_text": scrape_result.text,
        "raw_html": scrape_result.raw_html,
    }


def run_match_hook(
    *,
    matcher_service: MatcherService,
    jd_text: str,
    resume_text: str,
    job_id: str | None = None,
    user_id: str | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    """Run match step as a tool-friendly hook."""
    result = matcher_service.match(
        jd_text=jd_text,
        resume_text=resume_text,
        job_id=job_id,
        user_id=user_id,
        url=url,
    )
    return {
        "match_score": result.match_score,
        "strengths": result.strengths,
        "gaps": result.gaps,
    }


def run_decision_hook(*, decision_service: DecisionService, match_score: float) -> dict[str, Any]:
    """Run decision step as a tool-friendly hook."""
    decision = decision_service.decide(match_score=match_score)
    return {
        "decision": decision.decision,
        "match_score": decision.match_score,
        "threshold": decision.threshold,
    }


def run_outreach_hook(
    *,
    outreach_service: OutreachService,
    jd_text: str,
    resume_highlights: list[str],
) -> dict[str, Any]:
    """Run outreach step as a tool-friendly hook."""
    message = outreach_service.generate_referral_message(
        jd_text=jd_text,
        resume_highlights=resume_highlights,
    )
    return {"message": message}
