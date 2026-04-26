"""Job fetching module for Hirex AI MVP.

Source-specific fetch logic lives under ``job_sources``.
This module exposes a tiny dispatcher for future multi-source support.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from job_sources.indeed_source import fetch_jobs_indeed as _fetch_jobs_indeed


def fetch_jobs(role: str, location: Optional[str] = None, limit: int = 10) -> List[Dict[str, str]]:
    """Fetch jobs from the configured source(s).

    For now, dispatches to Indeed only.
    """
    return _fetch_jobs_indeed(target_role=role, location=location, limit=limit)


def fetch_jobs_indeed(target_role: str, location: Optional[str] = None, limit: int = 10) -> List[Dict[str, str]]:
    """Backward-compatible wrapper retained for existing callers."""
    return _fetch_jobs_indeed(target_role=target_role, location=location, limit=limit)
