from __future__ import annotations

from pydantic import BaseModel, Field


class ProfileDocument(BaseModel):
    user_id: str
    skills: list[str] = Field(default_factory=list)
    resume_url: str | None = None
    parsed_resume_json: dict = Field(default_factory=dict)


class ProfileResponse(BaseModel):
    user_id: str
    skills: list[str]
    resume_url: str | None
    parsed_resume_json: dict
