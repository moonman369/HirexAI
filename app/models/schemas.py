"""API schemas for job ingestion and outreach endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class JobIngestionRequest(BaseModel):
    user_id: str = Field(min_length=1)
    job_urls: list[str] = Field(min_length=1)
    resume_text: str | None = None
    resume_metadata: dict[str, Any] | None = None


class JobIngestionResponse(BaseModel):
    user_id: str
    accepted_jobs: int
    job_ids: list[str]
    status: str = "QUEUED"


class JobStatusResponse(BaseModel):
    job: dict[str, Any]


class OutreachSyncRequest(BaseModel):
    job_id: str | None = None


class OutreachActionResponse(BaseModel):
    result: dict[str, Any]
