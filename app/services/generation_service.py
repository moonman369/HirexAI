from __future__ import annotations

from typing import Any

from generator import generate_personalized_content


def generate_content(
    resume_json: dict[str, Any],
    job: dict[str, str],
    match_result: dict[str, Any],
) -> dict[str, Any]:
    return generate_personalized_content(resume_json, job, match_result)
