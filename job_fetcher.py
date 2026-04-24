"""Job fetching module for Hirex AI MVP.

Uses a single source (Indeed) as required for Phase 1.
The fetcher is intentionally wrapped behind a simple function to allow
future multi-source expansion.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup


INDEED_BASE = "https://www.indeed.com/jobs"


def _build_query_url(target_role: str, location: Optional[str], start: int = 0) -> str:
    query = quote_plus(target_role)
    loc = quote_plus(location or "")
    return f"{INDEED_BASE}?q={query}&l={loc}&start={start}"


def fetch_jobs_indeed(target_role: str, location: Optional[str] = None, limit: int = 10) -> List[Dict[str, str]]:
    """Fetch up to `limit` jobs from Indeed search results."""
    limit = max(1, min(limit, 10))

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    }

    jobs: List[Dict[str, str]] = []
    # Pull up to two pages to collect enough cards.
    for start in (0, 10):
        if len(jobs) >= limit:
            break

        url = _build_query_url(target_role, location, start=start)
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select("div.job_seen_beacon")

        for card in cards:
            if len(jobs) >= limit:
                break

            title_el = card.select_one("h2.jobTitle a span")
            link_el = card.select_one("h2.jobTitle a")
            company_el = card.select_one("span.companyName")
            location_el = card.select_one("div.companyLocation")
            desc_el = card.select_one("div.job-snippet")

            rel_url = link_el.get("href", "") if link_el else ""
            job_url = f"https://www.indeed.com{rel_url}" if rel_url.startswith("/") else rel_url

            jobs.append(
                {
                    "title": title_el.get_text(strip=True) if title_el else "Unknown Title",
                    "company": company_el.get_text(strip=True) if company_el else "Unknown Company",
                    "location": location_el.get_text(strip=True) if location_el else "Unknown Location",
                    "job_url": job_url,
                    "job_description": desc_el.get_text(" ", strip=True) if desc_el else "",
                }
            )

    # Deduplicate by URL and title/company fallback key.
    seen = set()
    deduped: List[Dict[str, str]] = []
    for job in jobs:
        key = job["job_url"] or f"{job['title']}::{job['company']}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)

    return deduped[:limit]
