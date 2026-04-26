from __future__ import annotations

import os
import tempfile
from typing import Any

import requests

from resume_parser import parse_resume_to_json


def parse_resume_from_file_path(pdf_path: str) -> dict[str, Any]:
    return parse_resume_to_json(pdf_path)


def parse_resume_from_pdf_bytes(pdf_bytes: bytes) -> dict[str, Any]:
    fd, temp_path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as tmp_file:
            tmp_file.write(pdf_bytes)
        return parse_resume_to_json(temp_path)
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


def parse_resume_from_url(resume_url: str) -> dict[str, Any]:
    response = requests.get(resume_url, timeout=30)
    response.raise_for_status()
    return parse_resume_from_pdf_bytes(response.content)
