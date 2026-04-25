from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class JobRunRequest(BaseModel):
    role: str = Field(min_length=2)
    location: str | None = None
    max_jobs: int = Field(default=8, ge=1, le=10)


class JobResult(BaseModel):
    job: dict
    match: dict
    generated: dict


class JobRunDocument(BaseModel):
    id: str | None = Field(default=None, alias="_id")
    user_id: str
    role: str
    location: str | None = None
    results: list[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
