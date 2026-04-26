from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from app.db.mongo import get_collection
from app.models.job_run_model import JobFilters
from app.services.generation_service import generate_content
from app.services.job_service import prepare_jobs
from app.services.match_service import compute_match
from app.services.resume_service import parse_resume_from_url


DEFAULT_FETCH_LIMIT = 8
logger = logging.getLogger(__name__)


def _ensure_profile_resume(profile: dict[str, Any]) -> dict[str, Any]:
    parsed = profile.get("parsed_resume_json") or {}
    if parsed:
        logger.info("job_agent.resume_cached user_id=%s", profile.get("user_id"))
        return parsed

    resume_url = profile.get("resume_url")
    if not resume_url:
        logger.error("job_agent.resume_missing user_id=%s", profile.get("user_id"))
        raise ValueError("No resume found in profile. Upload resume before running jobs.")

    logger.info("job_agent.resume_parse_from_url user_id=%s", profile.get("user_id"))
    parsed = parse_resume_from_url(resume_url)
    profiles = get_collection("profiles")
    profiles.update_one(
        {"user_id": profile["user_id"]},
        {"$set": {"parsed_resume_json": parsed, "skills": parsed.get("skills", [])}},
    )
    return parsed


def _apply_job_filters(jobs: list[dict[str, Any]], filters: JobFilters) -> list[dict[str, Any]]:
    filtered = jobs

    if filters.companies:
        company_filters = [company.strip().lower() for company in filters.companies if company.strip()]
        filtered = [
            job
            for job in filtered
            if any(company in str(job.get("company", "")).lower() for company in company_filters)
        ]

    if filters.seniority:
        seniority = filters.seniority.strip().lower()
        filtered = [
            job
            for job in filtered
            if seniority in f"{job.get('title', '')} {job.get('job_description', '')}".lower()
        ]

    if filters.job_type:
        job_type = filters.job_type.strip().lower()
        filtered = [
            job
            for job in filtered
            if job_type in f"{job.get('title', '')} {job.get('job_description', '')}".lower()
        ]

    if filters.remote is not None:
        def _is_remote(job: dict[str, Any]) -> bool:
            text = f"{job.get('location', '')} {job.get('job_description', '')}".lower()
            return "remote" in text or "work from home" in text or "wfh" in text

        filtered = [job for job in filtered if _is_remote(job) == filters.remote]

    if filters.date_posted:
        jobs_with_date = [job for job in filtered if job.get("date_posted")]
        if jobs_with_date:
            filtered = [job for job in jobs_with_date if str(job.get("date_posted")) == filters.date_posted]

    return filtered


def _build_result_item(
    job: dict[str, Any],
    match_result: dict[str, Any],
    generated: dict[str, Any],
) -> dict[str, Any]:
    raw_score = match_result.get("score", 0)
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.0

    missing_skills = [
        str(skill).strip()
        for skill in match_result.get("missing_skills", [])
        if str(skill).strip()
    ]
    resume_suggestions = [
        str(suggestion).strip()
        for suggestion in generated.get("resume_bullet_improvements", [])
        if str(suggestion).strip()
    ]

    return {
        "title": str(job.get("title", "")).strip(),
        "company": str(job.get("company", "")).strip(),
        "location": str(job.get("location", "")).strip(),
        "job_url": str(job.get("job_url", "")).strip(),
        "score": score,
        "missing_skills": missing_skills,
        "reasoning": str(match_result.get("reasoning", "")).strip(),
        "resume_suggestions": resume_suggestions,
        "cover_letter": str(generated.get("cover_letter", "")).strip(),
    }


def _normalize_result_item(item: dict[str, Any]) -> dict[str, Any]:
    if {"job", "match", "generated"}.issubset(item.keys()):
        return _build_result_item(
            job=item.get("job", {}),
            match_result=item.get("match", {}),
            generated=item.get("generated", {}),
        )

    raw_score = item.get("score", 0)
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.0

    missing_skills = [str(skill).strip() for skill in item.get("missing_skills", []) if str(skill).strip()]
    resume_suggestions = [
        str(suggestion).strip()
        for suggestion in item.get("resume_suggestions", [])
        if str(suggestion).strip()
    ]

    return {
        "title": str(item.get("title", "")).strip(),
        "company": str(item.get("company", "")).strip(),
        "location": str(item.get("location", "")).strip(),
        "job_url": str(item.get("job_url", "")).strip(),
        "score": score,
        "missing_skills": missing_skills,
        "reasoning": str(item.get("reasoning", "")).strip(),
        "resume_suggestions": resume_suggestions,
        "cover_letter": str(item.get("cover_letter", "")).strip(),
    }


def _serialize_run_doc(run: dict[str, Any]) -> dict[str, Any]:
    raw_results = run.get("results", [])
    normalized_results = [_normalize_result_item(item) for item in raw_results if isinstance(item, dict)]

    return {
        "run_id": str(run.get("_id")),
        "role": str(run.get("role") or ""),
        "location": run.get("location"),
        "filters": run.get("filters") or {},
        "results": normalized_results,
        "created_at": run.get("created_at") or datetime.utcnow(),
    }


def run_job_search_agent(
    user_id: str,
    role: str,
    location: str | None,
    filters: JobFilters | None = None,
) -> dict[str, Any]:
    filters = filters or JobFilters()
    logger.info(
        "job_agent.run_start user_id=%s role=%s location=%s filters=%s",
        user_id,
        role,
        location,
        filters.model_dump(),
    )

    profiles = get_collection("profiles")
    job_runs = get_collection("job_runs")

    profile = profiles.find_one({"user_id": user_id})
    if not profile:
        logger.error("job_agent.profile_missing user_id=%s", user_id)
        raise ValueError("User profile not found. Create/upload resume first.")

    try:
        resume_json = _ensure_profile_resume(profile)
        jobs = prepare_jobs(role=role, location=location, limit=DEFAULT_FETCH_LIMIT)
        logger.info("job_agent.jobs_fetched user_id=%s fetched_count=%s", user_id, len(jobs))
        jobs = _apply_job_filters(jobs, filters)
        logger.info("job_agent.jobs_filtered user_id=%s filtered_count=%s", user_id, len(jobs))
    except Exception:
        logger.exception("job_agent.prep_failed user_id=%s role=%s", user_id, role)
        raise

    results: list[dict[str, Any]] = []
    try:
        for job in jobs:
            match_result = compute_match(resume_json, job.get("job_description", ""))
            generated = generate_content(resume_json, job, match_result)
            results.append(_build_result_item(job, match_result, generated))
    except Exception:
        logger.exception("job_agent.scoring_or_generation_failed user_id=%s role=%s", user_id, role)
        raise

    results.sort(key=lambda item: item.get("score", 0), reverse=True)

    run_doc = {
        "user_id": user_id,
        "role": role,
        "location": location,
        "filters": filters.model_dump(),
        "results": results,
        "created_at": datetime.utcnow(),
    }
    try:
        insert_result = job_runs.insert_one(run_doc)
    except Exception:
        logger.exception("job_agent.persist_failed user_id=%s role=%s", user_id, role)
        raise

    logger.info(
        "job_agent.run_success user_id=%s run_id=%s results_count=%s",
        user_id,
        str(insert_result.inserted_id),
        len(results),
    )

    return {
        "run_id": str(insert_result.inserted_id),
        "results": results,
    }


def get_job_history(user_id: str) -> list[dict[str, Any]]:
    job_runs = get_collection("job_runs")
    runs = job_runs.find({"user_id": user_id}).sort("created_at", -1)
    return [_serialize_run_doc(run) for run in runs]


def get_job_run(user_id: str, run_id: str) -> dict[str, Any] | None:
    job_runs = get_collection("job_runs")
    try:
        oid = ObjectId(run_id)
    except InvalidId:
        return None

    run = job_runs.find_one({"_id": oid, "user_id": user_id})
    if not run:
        return None
    return _serialize_run_doc(run)
