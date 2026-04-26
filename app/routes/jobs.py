from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.job_agent import get_job_history, get_job_run, run_job_search_agent
from app.models.job_run_model import JobHistoryResponse, JobRunRead, JobRunRequest, JobRunResponse
from app.utils.auth_utils import get_current_user_claims


router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)


@router.post("/run", response_model=JobRunResponse)
def run_jobs(payload: JobRunRequest, claims: dict = Depends(get_current_user_claims)) -> JobRunResponse:
    user_id = claims["sub"]
    logger.info(
        "jobs_run.start user_id=%s role=%s location=%s filters=%s",
        user_id,
        payload.role,
        payload.location,
        payload.filters.model_dump(),
    )
    try:
        result = run_job_search_agent(
            user_id=user_id,
            role=payload.role,
            location=payload.location,
            filters=payload.filters,
        )
        response = JobRunResponse.model_validate(result)
        logger.info(
            "jobs_run.success user_id=%s run_id=%s results_count=%s",
            user_id,
            response.run_id,
            len(response.results),
        )
        return response
    except ValueError as exc:
        logger.error("jobs_run.validation_error user_id=%s error=%s", user_id, str(exc))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("jobs_run.failed user_id=%s role=%s", user_id, payload.role)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Job search pipeline failed due to an upstream dependency",
        ) from exc


@router.get("/history", response_model=JobHistoryResponse)
def history(claims: dict = Depends(get_current_user_claims)) -> JobHistoryResponse:
    user_id = claims["sub"]
    logger.info("jobs_history.start user_id=%s", user_id)
    runs = get_job_history(user_id=user_id)
    logger.info("jobs_history.success user_id=%s count=%s", user_id, len(runs))
    return JobHistoryResponse(count=len(runs), runs=[JobRunRead.model_validate(run) for run in runs])


@router.get("/{run_id}", response_model=JobRunRead)
def run_details(run_id: str, claims: dict = Depends(get_current_user_claims)) -> JobRunRead:
    user_id = claims["sub"]
    logger.info("jobs_details.start user_id=%s run_id=%s", user_id, run_id)
    run = get_job_run(user_id=user_id, run_id=run_id)
    if not run:
        logger.error("jobs_details.not_found user_id=%s run_id=%s", user_id, run_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    logger.info("jobs_details.success user_id=%s run_id=%s", user_id, run_id)
    return JobRunRead.model_validate(run)
