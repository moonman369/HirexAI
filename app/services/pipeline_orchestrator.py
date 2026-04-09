"""Pipeline orchestration for end-to-end per-job processing."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.db.jobs import JobsRepository
from app.db.outreach import OutreachRepository

logger = logging.getLogger(__name__)


class JobScraper(Protocol):
    """Scrapes a job description text from a job URL."""

    def scrape(self, *, job_id: str, user_id: str, url: str) -> str:
        """Return the raw job description text."""


class JobMatcher(Protocol):
    """Matches user profile data to job description text."""

    def match(
        self,
        *,
        job_id: str,
        user_id: str,
        url: str,
        jd_text: str,
    ) -> float:
        """Return a match score normalized to 0.0-1.0."""


class OutreachGenerator(Protocol):
    """Generates an outreach message for shortlisted jobs."""

    def generate(
        self,
        *,
        job_id: str,
        user_id: str,
        url: str,
        jd_text: str,
        match_score: float,
    ) -> str:
        """Return outreach text for the user + job pair."""


@dataclass(slots=True)
class PipelineJob:
    """Minimal payload required for the pipeline."""

    job_id: str
    user_id: str
    url: str
    status: str = "NEW"
    metadata: dict[str, Any] = field(default_factory=dict)


class PipelineOrchestrator:
    """Runs each job through scrape, match, shortlist/reject, and outreach stages."""

    def __init__(
        self,
        *,
        scraper: JobScraper,
        matcher: JobMatcher,
        outreach_generator: OutreachGenerator,
        jobs_repository: JobsRepository | None = None,
        outreach_repository: OutreachRepository | None = None,
        shortlist_threshold: float = 0.75,
    ) -> None:
        self.scraper = scraper
        self.matcher = matcher
        self.outreach_generator = outreach_generator
        self.jobs_repository = jobs_repository or JobsRepository()
        self.outreach_repository = outreach_repository or OutreachRepository()
        self.shortlist_threshold = shortlist_threshold

    def process_jobs(self, jobs: list[PipelineJob]) -> None:
        """Process jobs independently so one failure does not stop others."""
        for job in jobs:
            try:
                self._process_single_job(job)
            except Exception:
                logger.exception(
                    "pipeline_job_failed job_id=%s user_id=%s url=%s",
                    job.job_id,
                    job.user_id,
                    job.url,
                )
                self.jobs_repository.update_job_processing(
                    job.job_id,
                    status="FAILED",
                    extra_fields={"error_stage": "PIPELINE"},
                )

    def _process_single_job(self, job: PipelineJob) -> None:
        jd_text = self._run_scrape_stage(job)
        match_score = self._run_match_stage(job, jd_text)

        if match_score < self.shortlist_threshold:
            self._run_reject_stage(job, match_score)
            return

        self._run_shortlist_stage(job, match_score)
        self._run_outreach_stage(job, jd_text, match_score)

    def _run_scrape_stage(self, job: PipelineJob) -> str:
        self._log_stage("SCRAPE", "start", job)
        try:
            jd_text = self.scraper.scrape(job_id=job.job_id, user_id=job.user_id, url=job.url)
            self.jobs_repository.update_job_processing(
                job.job_id,
                jd_text=jd_text,
                status="SCRAPED",
                extra_fields={"pipeline_stage": "SCRAPED"},
            )
            self._log_stage("SCRAPE", "end", job)
            return jd_text
        except Exception:
            self._log_stage_error("SCRAPE", job)
            self.jobs_repository.update_job_processing(
                job.job_id,
                status="FAILED",
                extra_fields={"error_stage": "SCRAPE"},
            )
            raise

    def _run_match_stage(self, job: PipelineJob, jd_text: str) -> float:
        self._log_stage("MATCH", "start", job)
        try:
            match_score = self.matcher.match(
                job_id=job.job_id,
                user_id=job.user_id,
                url=job.url,
                jd_text=jd_text,
            )
            self.jobs_repository.update_job_processing(
                job.job_id,
                match_score=match_score,
                status="MATCHED",
                extra_fields={"pipeline_stage": "MATCHED"},
            )
            self._log_stage("MATCH", "end", job)
            return match_score
        except Exception:
            self._log_stage_error("MATCH", job)
            self.jobs_repository.update_job_processing(
                job.job_id,
                status="FAILED",
                extra_fields={"error_stage": "MATCH"},
            )
            raise

    def _run_reject_stage(self, job: PipelineJob, match_score: float) -> None:
        self._log_stage("SHORTLIST_DECISION", "start", job)
        self.jobs_repository.update_job_processing(
            job.job_id,
            status="REJECTED",
            extra_fields={"decision_reason": "below_threshold", "threshold": self.shortlist_threshold},
        )
        self._log_stage(
            "SHORTLIST_DECISION",
            "end",
            job,
            extra={"decision": "REJECTED", "match_score": match_score},
        )

    def _run_shortlist_stage(self, job: PipelineJob, match_score: float) -> None:
        self._log_stage("SHORTLIST_DECISION", "start", job)
        self.jobs_repository.update_job_processing(
            job.job_id,
            status="SHORTLISTED",
            extra_fields={"threshold": self.shortlist_threshold},
        )
        self._log_stage(
            "SHORTLIST_DECISION",
            "end",
            job,
            extra={"decision": "SHORTLISTED", "match_score": match_score},
        )

    def _run_outreach_stage(self, job: PipelineJob, jd_text: str, match_score: float) -> None:
        self._log_stage("OUTREACH", "start", job)
        try:
            message = self.outreach_generator.generate(
                job_id=job.job_id,
                user_id=job.user_id,
                url=job.url,
                jd_text=jd_text,
                match_score=match_score,
            )
            self.outreach_repository.store_outreach_message(
                job_id=job.job_id,
                user_id=job.user_id,
                message=message,
                metadata={"url": job.url, "match_score": match_score},
            )
            self.jobs_repository.update_job_processing(
                job.job_id,
                status="OUTREACH_GENERATED",
                extra_fields={"pipeline_stage": "OUTREACH_GENERATED"},
            )
            self._log_stage("OUTREACH", "end", job)
        except Exception:
            self._log_stage_error("OUTREACH", job)
            self.jobs_repository.update_job_processing(
                job.job_id,
                status="FAILED",
                extra_fields={"error_stage": "OUTREACH"},
            )
            raise

    def _log_stage(
        self,
        stage: str,
        event: str,
        job: PipelineJob,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        context = {"job_id": job.job_id, "user_id": job.user_id, "url": job.url, **(extra or {})}
        logger.info("pipeline_stage=%s event=%s context=%s", stage, event, context)

    def _log_stage_error(self, stage: str, job: PipelineJob) -> None:
        logger.exception(
            "pipeline_stage=%s event=error job_id=%s user_id=%s url=%s",
            stage,
            job.job_id,
            job.user_id,
            job.url,
        )
