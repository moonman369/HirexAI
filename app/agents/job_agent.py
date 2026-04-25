from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from app.db.mongo import get_collection
from app.services.generation_service import generate_content
from app.services.job_service import prepare_jobs
from app.services.match_service import compute_match
from app.services.resume_service import parse_resume_from_url


def _ensure_profile_resume(profile: dict[str, Any]) -> dict[str, Any]:
    parsed = profile.get("parsed_resume_json") or {}
    if parsed:
        return parsed

    resume_url = profile.get("resume_url")
    if not resume_url:
        raise ValueError("No resume found in profile. Upload resume before running jobs.")

    parsed = parse_resume_from_url(resume_url)
    profiles = get_collection("profiles")
    profiles.update_one(
        {"user_id": profile["user_id"]},
        {"$set": {"parsed_resume_json": parsed, "skills": parsed.get("skills", [])}},
    )
    return parsed


def run_job_search_agent(user_id: str, role: str, location: str | None, max_jobs: int) -> dict[str, Any]:
    profiles = get_collection("profiles")
    job_runs = get_collection("job_runs")

    profile = profiles.find_one({"user_id": user_id})
    if not profile:
        raise ValueError("User profile not found. Create/upload resume first.")

    resume_json = _ensure_profile_resume(profile)
    jobs = prepare_jobs(role=role, location=location, limit=max_jobs)

    results: list[dict[str, Any]] = []
    for job in jobs:
        match_result = compute_match(resume_json, job.get("job_description", ""))
        generated = generate_content(resume_json, job, match_result)
        results.append({"job": job, "match": match_result, "generated": generated})

    results.sort(key=lambda item: item.get("match", {}).get("score", 0), reverse=True)

    run_doc = {
        "user_id": user_id,
        "role": role,
        "location": location,
        "results": results,
        "created_at": datetime.utcnow(),
    }
    insert_result = job_runs.insert_one(run_doc)

    return {
        "run_id": str(insert_result.inserted_id),
        "user_id": user_id,
        "role": role,
        "location": location,
        "results": results,
        "created_at": run_doc["created_at"].isoformat(),
    }


def get_job_history(user_id: str) -> list[dict[str, Any]]:
    job_runs = get_collection("job_runs")
    runs = job_runs.find({"user_id": user_id}).sort("created_at", -1)
    output = []
    for run in runs:
        run["_id"] = str(run["_id"])
        output.append(run)
    return output


def get_job_run(user_id: str, run_id: str) -> dict[str, Any] | None:
    job_runs = get_collection("job_runs")
    try:
        oid = ObjectId(run_id)
    except InvalidId:
        return None

    run = job_runs.find_one({"_id": oid, "user_id": user_id})
    if not run:
        return None
    run["_id"] = str(run["_id"])
    return run
