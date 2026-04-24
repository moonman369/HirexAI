"""CLI entrypoint for Hirex AI MVP."""

from __future__ import annotations

import argparse
from typing import Any, Dict, List

from generator import generate_personalized_content
from jd_processor import clean_job_description
from job_fetcher import fetch_jobs_indeed
from matcher import match_resume_to_job
from resume_parser import parse_resume_to_json


def _print_job_result(job: Dict[str, str], match_result: Dict[str, Any], generated: Dict[str, Any]) -> None:
    print("\n" + "=" * 80)
    print(f"Title: {job.get('title', '')}")
    print(f"Company: {job.get('company', '')}")
    print(f"Location: {job.get('location', '')}")
    print(f"Match Score: {match_result.get('score', 0)}")
    print(f"Missing Skills: {', '.join(match_result.get('missing_skills', [])) or 'None'}")

    print("\nTailored Resume Suggestions:")
    for idx, bullet in enumerate(generated.get("resume_bullet_improvements", []), start=1):
        print(f"  {idx}. {bullet}")

    print("\nCover Letter:")
    print(generated.get("cover_letter", ""))

    print(f"\nApply Link: {job.get('job_url', '')}")


def run_pipeline(resume_pdf: str, target_role: str, location: str | None, max_jobs: int) -> List[Dict[str, Any]]:
    """Orchestrate the complete Phase 1 flow and return structured results."""
    resume_json = parse_resume_to_json(resume_pdf)
    jobs = fetch_jobs_indeed(target_role=target_role, location=location, limit=max_jobs)

    results: List[Dict[str, Any]] = []
    for job in jobs:
        cleaned_jd = clean_job_description(job.get("job_description", ""))
        match_result = match_resume_to_job(resume_json, cleaned_jd)
        generated = generate_personalized_content(resume_json, job, match_result)

        job_result = {
            "job": job,
            "match": match_result,
            "generated": generated,
        }
        results.append(job_result)

        _print_job_result(job, match_result, generated)

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hirex AI - AI Job Hunter Agent MVP")
    parser.add_argument("resume_pdf", help="Path to resume PDF file")
    parser.add_argument("target_role", help="Target job role keyword(s)")
    parser.add_argument("--location", default=None, help="Preferred location (optional)")
    parser.add_argument("--max-jobs", type=int, default=8, help="Max jobs to fetch (1-10)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_pipeline(
        resume_pdf=args.resume_pdf,
        target_role=args.target_role,
        location=args.location,
        max_jobs=max(1, min(10, args.max_jobs)),
    )


if __name__ == "__main__":
    main()
