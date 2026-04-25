from __future__ import annotations

import tempfile
from typing import Any

import requests

from resume_parser import parse_resume_to_json


def parse_resume_from_file_path(pdf_path: str) -> dict[str, Any]:
    return parse_resume_to_json(pdf_path)


def parse_resume_from_url(resume_url: str) -> dict[str, Any]:
    response = requests.get(resume_url, timeout=30)
    response.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(response.content)
        tmp.flush()
        return parse_resume_to_json(tmp.name)
