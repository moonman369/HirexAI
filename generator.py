"""Content generation for resume bullets and short cover letters."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


def _offline_suggestions(match_result: Dict[str, Any], job: Dict[str, str]) -> Dict[str, Any]:
    missing = match_result.get("missing_skills", [])[:3]
    bullets = [
        f"Highlight measurable impact in projects relevant to {job.get('title', 'the role')}.",
        "Add one bullet showing collaboration with cross-functional stakeholders.",
    ]
    if missing:
        bullets.append(f"If accurate, include hands-on examples with: {', '.join(missing)}.")

    cover_letter = (
        f"Dear Hiring Team at {job.get('company', 'your company')},\n"
        f"I am excited to apply for the {job.get('title', 'position')} role.\n"
        "My background includes delivering practical, outcome-driven technical work.\n"
        "I enjoy collaborating across teams to ship reliable solutions quickly.\n"
        "I would value the chance to contribute to your team and mission.\n"
        "Thank you for your consideration."
    )

    return {
        "resume_bullet_improvements": bullets[:3],
        "cover_letter": cover_letter,
    }


def _llm_generation(resume_json: Dict[str, Any], job: Dict[str, str], match_result: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _offline_suggestions(match_result, job)

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    prompt = (
        "Given resume JSON, job summary, and match analysis, return strict JSON with keys: "
        'resume_bullet_improvements (2-3 item list), cover_letter (5-6 lines).\n\n'
        f"Resume JSON:\n{json.dumps(resume_json)[:6000]}\n\n"
        f"Job:\n{json.dumps(job)[:3000]}\n\n"
        f"Match:\n{json.dumps(match_result)}"
    )

    response = client.responses.create(
        model=os.getenv("HIREX_MODEL", "gpt-4.1-mini"),
        input=prompt,
        temperature=0.4,
    )

    parsed = json.loads(response.output_text.strip())
    bullets = parsed.get("resume_bullet_improvements", [])[:3]
    return {
        "resume_bullet_improvements": [str(b).strip() for b in bullets if str(b).strip()],
        "cover_letter": str(parsed.get("cover_letter", "")).strip(),
    }


def generate_personalized_content(
    resume_json: Dict[str, Any],
    job: Dict[str, str],
    match_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Public entrypoint for personalized content generation."""
    return _llm_generation(resume_json, job, match_result)
