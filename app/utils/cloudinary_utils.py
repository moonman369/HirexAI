from __future__ import annotations

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile

from app.config import settings


_configured = False


def _configure_cloudinary() -> None:
    global _configured
    if _configured:
        return
    if not (
        settings.cloudinary_cloud_name
        and settings.cloudinary_api_key
        and settings.cloudinary_api_secret
    ):
        raise HTTPException(
            status_code=500,
            detail="Cloudinary is not configured. Set cloudinary credentials in environment.",
        )

    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    _configured = True


def upload_resume_pdf(file: UploadFile, user_id: str) -> str:
    _configure_cloudinary()
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    file.file.seek(0)
    response = cloudinary.uploader.upload(
        file.file,
        resource_type="raw",
        folder="hirexai/resumes",
        public_id=f"{user_id}-resume",
        overwrite=True,
    )
    url = response.get("secure_url")
    if not url:
        raise HTTPException(status_code=500, detail="Cloudinary upload did not return secure_url")
    return str(url)
