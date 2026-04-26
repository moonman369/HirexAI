from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.config import settings
from app.db.mongo import get_collection
from app.services.resume_service import parse_resume_from_pdf_bytes
from app.utils.auth_utils import get_current_user_claims
from app.utils.cloudinary_utils import upload_resume_pdf


router = APIRouter(prefix="/profile", tags=["profile"])
logger = logging.getLogger(__name__)


@router.get("")
def get_profile(claims: dict = Depends(get_current_user_claims)) -> dict:
    profiles = get_collection("profiles")
    profile = profiles.find_one({"user_id": claims["sub"]})
    if not profile:
        return {
            "user_id": claims["sub"],
            "skills": [],
            "resume_url": None,
            "parsed_resume_json": {},
        }

    profile.pop("_id", None)
    return profile


@router.post("/upload-resume")
def upload_resume(
    file: UploadFile = File(...),
    claims: dict = Depends(get_current_user_claims),
) -> dict:
    user_id = claims["sub"]
    logger.info(
        "resume_upload.start user_id=%s filename=%s content_type=%s",
        user_id,
        file.filename,
        file.content_type,
    )
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        logger.error(
            "resume_upload.invalid_content_type user_id=%s content_type=%s",
            user_id,
            file.content_type,
        )
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    file.file.seek(0)
    pdf_bytes = file.file.read()
    if not pdf_bytes:
        logger.error("resume_upload.empty_file user_id=%s filename=%s", user_id, file.filename)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        parsed_resume = parse_resume_from_pdf_bytes(pdf_bytes)
    except Exception as exc:
        logger.exception("resume_upload.parse_failed user_id=%s filename=%s", user_id, file.filename)
        raise HTTPException(
            status_code=400,
            detail="Failed to parse resume PDF. Ensure it contains extractable text.",
        ) from exc

    resume_url: str | None = None
    if (
        settings.cloudinary_cloud_name
        and settings.cloudinary_api_key
        and settings.cloudinary_api_secret
    ):
        try:
            resume_url = upload_resume_pdf(file, user_id=user_id)
            logger.info("resume_upload.cloudinary_uploaded user_id=%s", user_id)
        except HTTPException:
            logger.exception("resume_upload.cloudinary_failed user_id=%s", user_id)
            raise

    profiles = get_collection("profiles")
    update = {
        "$set": {
            "user_id": user_id,
            "resume_url": resume_url,
            "parsed_resume_json": parsed_resume,
            "skills": parsed_resume.get("skills", []),
        }
    }
    try:
        profiles.update_one({"user_id": user_id}, update, upsert=True)
    except Exception as exc:
        logger.exception("resume_upload.db_update_failed user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Failed to save profile data") from exc

    logger.info(
        "resume_upload.success user_id=%s skills_count=%s has_resume_url=%s",
        user_id,
        len(parsed_resume.get("skills", [])),
        bool(resume_url),
    )

    return {
        "message": "Resume uploaded and parsed successfully",
        "resume_url": resume_url,
        "skills": parsed_resume.get("skills", []),
    }


@router.get("/resume")
def get_resume(claims: dict = Depends(get_current_user_claims)) -> dict:
    profiles = get_collection("profiles")
    profile = profiles.find_one({"user_id": claims["sub"]})
    if not profile or (not profile.get("resume_url") and not profile.get("parsed_resume_json")):
        raise HTTPException(status_code=404, detail="Resume not found")

    return {
        "resume_url": profile.get("resume_url"),
        "parsed_resume_json": profile.get("parsed_resume_json", {}),
    }
