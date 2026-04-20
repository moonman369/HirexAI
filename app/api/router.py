from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.encoders import jsonable_encoder

from app.db.jobs import JobsRepository
from app.db.users import UsersRepository
from app.models.schemas import (
    JobIngestionRequest,
    JobIngestionResponse,
    JobStatusResponse,
    OutreachActionResponse,
    OutreachSyncRequest,
)
from app.services.manual_outreach_service import ManualOutreachService
from app.services.pipeline_orchestrator import PipelineJob
from app.services.runtime import build_pipeline_orchestrator, validate_runtime_configuration

logger = logging.getLogger(__name__)

api_router = APIRouter()


def _run_pipeline_jobs(jobs: list[PipelineJob]) -> None:
    if not jobs:
        return

    logger.info("pipeline_background event=start jobs=%s", len(jobs))
    try:
        orchestrator = build_pipeline_orchestrator()
        orchestrator.process_jobs(jobs)
    except Exception:
        logger.exception("pipeline_background event=failed jobs=%s", len(jobs))
        raise
    finally:
        logger.info("pipeline_background event=end jobs=%s", len(jobs))


@api_router.post("/jobs", response_model=JobIngestionResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_jobs(payload: JobIngestionRequest, background_tasks: BackgroundTasks) -> JobIngestionResponse:
    logger.info("api_event=ingest_jobs_start user_id=%s incoming_urls=%s", payload.user_id, len(payload.job_urls))

    try:
        validate_runtime_configuration()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    normalized_urls = [url.strip() for url in payload.job_urls if isinstance(url, str) and url.strip()]
    if not normalized_urls:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="job_urls must include at least one URL")

    users_repository = UsersRepository()
    resume_text = (payload.resume_text or "").strip()
    if resume_text:
        users_repository.upsert_user_resume(
            payload.user_id,
            resume_text,
            resume_metadata=payload.resume_metadata,
        )
    else:
        stored_resume_text = users_repository.get_resume_text(payload.user_id)
        if not stored_resume_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="resume_text is required for new users or when no stored resume exists",
            )
        resume_text = stored_resume_text

    jobs_repository = JobsRepository()
    job_documents: list[dict[str, str]] = []
    pipeline_jobs: list[PipelineJob] = []
    for url in normalized_urls:
        job_id = str(uuid4())
        job_documents.append(
            {
                "job_id": job_id,
                "user_id": payload.user_id,
                "url": url,
                "status": "NEW",
                "pipeline_stage": "NEW",
            }
        )
        pipeline_jobs.append(
            PipelineJob(
                job_id=job_id,
                user_id=payload.user_id,
                url=url,
                resume_text=resume_text,
            )
        )

    jobs_repository.insert_jobs(job_documents)
    background_tasks.add_task(_run_pipeline_jobs, pipeline_jobs)

    logger.info("api_event=ingest_jobs_queued user_id=%s queued_jobs=%s", payload.user_id, len(pipeline_jobs))
    return JobIngestionResponse(
        user_id=payload.user_id,
        accepted_jobs=len(pipeline_jobs),
        job_ids=[job.job_id for job in pipeline_jobs],
    )


@api_router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    try:
        job = JobsRepository().get_job_by_id(job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return JobStatusResponse(job=jsonable_encoder(job))


@api_router.post("/outreach/{job_id}/send-connections", response_model=OutreachActionResponse)
def send_connection_requests(job_id: str) -> OutreachActionResponse:
    try:
        result = ManualOutreachService().send_connection_requests(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return OutreachActionResponse(result=result)


@api_router.post("/outreach/sync", response_model=OutreachActionResponse)
def sync_connection_statuses(payload: OutreachSyncRequest) -> OutreachActionResponse:
    try:
        result = ManualOutreachService().sync_connection_statuses(payload.job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return OutreachActionResponse(result=result)


@api_router.post("/outreach/{job_id}/generate-referrals", response_model=OutreachActionResponse)
def generate_referral_drafts(job_id: str) -> OutreachActionResponse:
    try:
        result = ManualOutreachService().generate_referral_drafts(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return OutreachActionResponse(result=result)


@api_router.post("/outreach/{job_id}/send-referrals", response_model=OutreachActionResponse)
def send_approved_referral_messages(job_id: str) -> OutreachActionResponse:
    try:
        result = ManualOutreachService().send_approved_referral_messages(job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return OutreachActionResponse(result=result)
