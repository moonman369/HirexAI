"""Job description processing utilities."""

from __future__ import annotations

import re
from bs4 import BeautifulSoup


def clean_job_description(description: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    text = BeautifulSoup(description or "", "html.parser").get_text(" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text
