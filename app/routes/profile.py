from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.db.mongo import get_collection
from app.services.resume_service import parse_resume_from_url
from app.utils.auth_utils import get_current_user_claims
from app.utils.cloudinary_utils import upload_resume_pdf


router = APIRouter(prefix="/profile", tags=["profile"])


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
    resume_url = upload_resume_pdf(file, user_id=user_id)
    parsed_resume = parse_resume_from_url(resume_url)

    profiles = get_collection("profiles")
    update = {
        "$set": {
            "user_id": user_id,
            "resume_url": resume_url,
            "parsed_resume_json": parsed_resume,
            "skills": parsed_resume.get("skills", []),
        }
    }
    profiles.update_one({"user_id": user_id}, update, upsert=True)

    return {
        "message": "Resume uploaded and parsed successfully",
        "resume_url": resume_url,
        "skills": parsed_resume.get("skills", []),
    }


@router.get("/resume")
def get_resume(claims: dict = Depends(get_current_user_claims)) -> dict:
    profiles = get_collection("profiles")
    profile = profiles.find_one({"user_id": claims["sub"]})
    if not profile or not profile.get("resume_url"):
        raise HTTPException(status_code=404, detail="Resume not found")

    return {
        "resume_url": profile.get("resume_url"),
        "parsed_resume_json": profile.get("parsed_resume_json", {}),
    }
