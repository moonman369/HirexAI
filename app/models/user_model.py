from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserDocument(BaseModel):
    id: str | None = Field(default=None, alias="_id")
    email: EmailStr
    password_hash: str
    auth_provider: str = "email"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: EmailStr
