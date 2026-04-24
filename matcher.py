"""Matching engine for Hirex AI MVP."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List


COMMON_SKILLS = {
    "python",
    "sql",
    "java",
    "javascript",
    "typescript",
    "aws",
    "docker",
    "kubernetes",
    "pandas",
    "numpy",
    "scikit-learn",
    "tensorflow",
    "pytorch",
    "react",
    "node",
    "git",
}


def _extract_jd_skills(job_description: str) -> List[str]:
    text = job_description.lower()
    return sorted([s for s in COMMON_SKILLS if s in text])


def _offline_match(resume_json: Dict[str, Any], job_description: str) -> Dict[str, Any]:
    resume_skills = {str(s).strip().lower() for s in resume_json.get("skills", [])}
    jd_skills = set(_extract_jd_skills(job_description))

    if not jd_skills:
        return {
            "score": 50,
            "missing_skills": [],
            "reasoning": "Job description had limited extractable skill terms.",
        }

    overlap = resume_skills & jd_skills
    missing = sorted(jd_skills - resume_skills)
    score = int((len(overlap) / max(len(jd_skills), 1)) * 100)

    return {
        "score": score,
        "missing_skills": missing,
        "reasoning": f"Matched {len(overlap)} of {len(jd_skills)} key skills.",
    }


def _llm_match(resume_json: Dict[str, Any], job_description: str) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _offline_match(resume_json, job_description)

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    prompt = (
        "Compare this resume JSON and job description. Return strict JSON: "
        '{"score": int(0-100), "missing_skills": [list], "reasoning": "short explanation"}.\n\n'
        f"Resume JSON:\n{json.dumps(resume_json)[:8000]}\n\n"
        f"Job Description:\n{job_description[:8000]}"
    )

    response = client.responses.create(
        model=os.getenv("HIREX_MODEL", "gpt-4.1-mini"),
        input=prompt,
        temperature=0.2,
    )
    result = json.loads(response.output_text.strip())

    score = int(result.get("score", 0))
    score = max(0, min(100, score))
    missing = [re.sub(r"\s+", " ", str(s)).strip() for s in result.get("missing_skills", [])]
    reasoning = re.sub(r"\s+", " ", str(result.get("reasoning", ""))).strip()

    return {"score": score, "missing_skills": missing, "reasoning": reasoning}


def match_resume_to_job(resume_json: Dict[str, Any], job_description: str) -> Dict[str, Any]:
    """Public entrypoint for matching logic."""
    return _llm_match(resume_json, job_description)
