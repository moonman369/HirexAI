"""Resume parsing utilities for Hirex AI MVP.

Phase 1 behavior:
- Extract text from a PDF file path.
- Convert free-form resume text into a flexible JSON-like dictionary.

Design notes for Phase 2:
- The LLM parsing function is isolated so providers can be swapped later.
- The fallback parser is deterministic and keeps the MVP runnable offline.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

from pypdf import PdfReader


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract and concatenate text from all pages of a PDF."""
    reader = PdfReader(pdf_path)
    page_text = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(page_text).strip()
    if not text:
        raise ValueError(f"No text found in PDF: {pdf_path}")
    return text


def _offline_resume_structuring(resume_text: str) -> Dict[str, Any]:
    """Simple heuristic structure extraction when no LLM is configured."""
    lines = [ln.strip() for ln in resume_text.splitlines() if ln.strip()]
    lower_text = resume_text.lower()

    skill_keywords = {
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
    found_skills = sorted([s for s in skill_keywords if s in lower_text])

    section_buckets = {
        "experience": [],
        "projects": [],
        "education": [],
    }
    current_section = None

    for line in lines:
        header = line.lower()
        if "experience" in header:
            current_section = "experience"
            continue
        if "project" in header:
            current_section = "projects"
            continue
        if "education" in header:
            current_section = "education"
            continue

        if current_section:
            section_buckets[current_section].append(line)

    return {
        "skills": found_skills,
        "experience": section_buckets["experience"][:15],
        "projects": section_buckets["projects"][:10],
        "education": section_buckets["education"][:10],
        "raw_text_excerpt": " ".join(lines[:30]),
    }


def _call_openai_for_resume_json(resume_text: str) -> Dict[str, Any]:
    """Use OpenAI Responses API if OPENAI_API_KEY is present; otherwise fallback."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _offline_resume_structuring(resume_text)

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    prompt = (
        "Convert this resume text into JSON with keys: skills (list), "
        "experience (list), projects (list), education (list). "
        "Only output valid JSON.\n\n"
        f"Resume:\n{resume_text[:12000]}"
    )

    response = client.responses.create(
        model=os.getenv("HIREX_MODEL", "gpt-4.1-mini"),
        input=prompt,
        temperature=0.2,
    )

    output_text = response.output_text.strip()
    parsed = json.loads(output_text)
    return {
        "skills": parsed.get("skills", []),
        "experience": parsed.get("experience", []),
        "projects": parsed.get("projects", []),
        "education": parsed.get("education", []),
    }


def parse_resume_to_json(pdf_path: str) -> Dict[str, Any]:
    """Public entrypoint for resume parsing."""
    text = extract_text_from_pdf(pdf_path)
    resume_json = _call_openai_for_resume_json(text)

    # Light normalization for downstream modules.
    resume_json["skills"] = [str(s).strip() for s in resume_json.get("skills", []) if str(s).strip()]
    for section in ("experience", "projects", "education"):
        resume_json[section] = [
            re.sub(r"\s+", " ", str(item)).strip()
            for item in resume_json.get(section, [])
            if str(item).strip()
        ]
    return resume_json
