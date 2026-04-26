from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.db.mongo import get_collection
from app.models.user_model import AuthResponse, UserCreate, UserLogin
from app.utils.auth_utils import create_access_token, get_current_user_claims, hash_password, verify_password


router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/signup", response_model=AuthResponse)
def signup(payload: UserCreate) -> AuthResponse:
    logger.info("signup.start email=%s", payload.email)
    try:
        users = get_collection("users")
        existing = users.find_one({"email": payload.email})
        if existing:
            logger.error("signup.duplicate_email email=%s", payload.email)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        user_doc = {
            "email": payload.email,
            "password_hash": hash_password(payload.password),
            "auth_provider": "email",
            "created_at": datetime.utcnow(),
        }
        result = users.insert_one(user_doc)
        user_id = str(result.inserted_id)

        token = create_access_token(user_id=user_id, email=payload.email)
        logger.info("signup.success user_id=%s email=%s", user_id, payload.email)
        return AuthResponse(access_token=token, user_id=user_id, email=payload.email)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("signup.failed email=%s", payload.email)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Signup failed") from exc


@router.post("/login", response_model=AuthResponse)
def login(payload: UserLogin) -> AuthResponse:
    logger.info("login.start email=%s", payload.email)
    try:
        users = get_collection("users")
        user = users.find_one({"email": payload.email})
        if not user or user.get("auth_provider") != "email":
            logger.error("login.invalid_credentials email=%s", payload.email)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if not verify_password(payload.password, user.get("password_hash", "")):
            logger.error("login.invalid_credentials email=%s", payload.email)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        user_id = str(user["_id"])
        token = create_access_token(user_id=user_id, email=payload.email)
        logger.info("login.success user_id=%s email=%s", user_id, payload.email)
        return AuthResponse(access_token=token, user_id=user_id, email=payload.email)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("login.failed email=%s", payload.email)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed") from exc


@router.post("/logout")
def logout(claims: dict = Depends(get_current_user_claims)) -> dict:
    user_id = claims.get("sub")
    if not user_id:
        logger.error("logout.missing_subject_claim")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token payload")

    logger.info("logout.success user_id=%s", user_id)
    return {"message": "Logged out successfully. Discard access token client-side."}


@router.get("/google")
def google_oauth_start() -> dict:
    if not settings.oauth_google_client_id:
        return {
            "message": "Google OAuth not configured",
            "configure": ["OAUTH_GOOGLE_CLIENT_ID", "OAUTH_GOOGLE_CLIENT_SECRET"],
        }

    params = {
        "client_id": settings.oauth_google_client_id,
        "redirect_uri": f"{settings.oauth_redirect_base_url}/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return {"auth_url": auth_url, "provider": "google"}


@router.get("/linkedin")
def linkedin_oauth_start() -> dict:
    if not settings.oauth_linkedin_client_id:
        return {
            "message": "LinkedIn OAuth not configured",
            "configure": ["OAUTH_LINKEDIN_CLIENT_ID", "OAUTH_LINKEDIN_CLIENT_SECRET"],
        }

    params = {
        "response_type": "code",
        "client_id": settings.oauth_linkedin_client_id,
        "redirect_uri": f"{settings.oauth_redirect_base_url}/auth/linkedin/callback",
        "scope": "openid profile email",
    }
    auth_url = f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"
    return {"auth_url": auth_url, "provider": "linkedin"}
