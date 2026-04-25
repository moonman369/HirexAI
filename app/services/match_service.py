from __future__ import annotations

from typing import Any

from matcher import match_resume_to_job


def compute_match(resume_json: dict[str, Any], job_description: str) -> dict[str, Any]:
    return match_resume_to_job(resume_json, job_description)
