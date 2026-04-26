from __future__ import annotations

import logging
from typing import Any

from jd_processor import clean_job_description
from job_fetcher import fetch_jobs_indeed


logger = logging.getLogger(__name__)


def fetch_jobs(role: str, location: str | None, limit: int) -> list[dict[str, str]]:
    logger.info("fetch_jobs.start role=%s location=%s limit=%s", role, location, limit)
    try:
        jobs = fetch_jobs_indeed(target_role=role, location=location, limit=limit)
        logger.info("fetch_jobs.success role=%s count=%s", role, len(jobs))
        return jobs
    except Exception:
        logger.exception("fetch_jobs.failed role=%s location=%s", role, location)
        raise


def normalize_job_description(raw_description: str) -> str:
    return clean_job_description(raw_description)


def prepare_jobs(role: str, location: str | None, limit: int) -> list[dict[str, Any]]:
    logger.info("prepare_jobs.start role=%s location=%s limit=%s", role, location, limit)
    jobs = fetch_jobs(role=role, location=location, limit=limit)
    for job in jobs:
        job["job_description"] = normalize_job_description(job.get("job_description", ""))
    logger.info("prepare_jobs.success role=%s normalized_count=%s", role, len(jobs))
    return jobs
