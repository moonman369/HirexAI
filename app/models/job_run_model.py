from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JobFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    companies: list[str] = Field(default_factory=list)
    seniority: str | None = None
    date_posted: Literal["24h", "7d", "30d"] | None = None
    job_type: str | None = None
    remote: bool | None = None


class JobRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=2)
    location: str | None = None
    filters: JobFilters = Field(default_factory=JobFilters)


class JobSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    company: str
    location: str
    job_url: str
    score: float
    missing_skills: list[str] = Field(default_factory=list)
    reasoning: str
    resume_suggestions: list[str] = Field(default_factory=list)
    cover_letter: str


class JobRunResponse(BaseModel):
    run_id: str
    results: list[JobSearchResult] = Field(default_factory=list)


class JobRunDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str | None = Field(default=None, alias="_id")
    user_id: str
    role: str
    location: str | None = None
    filters: JobFilters = Field(default_factory=JobFilters)
    results: list[JobSearchResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class JobRunRead(BaseModel):
    run_id: str
    role: str
    location: str | None = None
    filters: JobFilters = Field(default_factory=JobFilters)
    results: list[JobSearchResult] = Field(default_factory=list)
    created_at: datetime


class JobHistoryResponse(BaseModel):
    count: int
    runs: list[JobRunRead] = Field(default_factory=list)
