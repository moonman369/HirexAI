from __future__ import annotations

from typing import Any

from jd_processor import clean_job_description
from job_fetcher import fetch_jobs_indeed


def fetch_jobs(role: str, location: str | None, limit: int) -> list[dict[str, str]]:
    return fetch_jobs_indeed(target_role=role, location=location, limit=limit)


def normalize_job_description(raw_description: str) -> str:
    return clean_job_description(raw_description)


def prepare_jobs(role: str, location: str | None, limit: int) -> list[dict[str, Any]]:
    jobs = fetch_jobs(role=role, location=location, limit=limit)
    for job in jobs:
        job["job_description"] = normalize_job_description(job.get("job_description", ""))
    return jobs
