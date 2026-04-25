from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.agents.job_agent import get_job_history, get_job_run, run_job_search_agent
from app.models.job_run_model import JobRunRequest
from app.utils.auth_utils import get_current_user_claims


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/run")
def run_jobs(payload: JobRunRequest, claims: dict = Depends(get_current_user_claims)) -> dict:
    try:
        return run_job_search_agent(
            user_id=claims["sub"],
            role=payload.role,
            location=payload.location,
            max_jobs=payload.max_jobs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/history")
def history(claims: dict = Depends(get_current_user_claims)) -> dict:
    runs = get_job_history(user_id=claims["sub"])
    return {"count": len(runs), "runs": runs}


@router.get("/{run_id}")
def run_details(run_id: str, claims: dict = Depends(get_current_user_claims)) -> dict:
    run = get_job_run(user_id=claims["sub"], run_id=run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
