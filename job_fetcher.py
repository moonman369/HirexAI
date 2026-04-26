"""Job fetching module for Hirex AI MVP.

Uses a single source (Indeed) as required for Phase 1.
The fetcher is intentionally wrapped behind a simple function to allow
future multi-source expansion.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

INDEED_SITE = "https://www.indeed.co.in"
INDEED_BASE = f"{INDEED_SITE}/jobs"
MAX_RETRIES = 3
logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Connection": "keep-alive",
}


def _build_query_url(target_role: str, location: Optional[str], start: int = 0) -> str:
    query = quote_plus(target_role)
    loc = quote_plus(location or "")
    return f"{INDEED_BASE}?q={query}&l={loc}&start={start}"


def _sleep_short_delay() -> None:
    delay_seconds = random.uniform(1, 3)
    logger.info("indeed_fetch.delay seconds=%.2f", delay_seconds)
    time.sleep(delay_seconds)


def _is_block_page(response_text: str) -> bool:
    text = (response_text or "").lower()
    indicators = (
        "captcha",
        "unusual traffic",
        "verify you are a human",
        "access denied",
        "bot detection",
    )
    return any(indicator in text for indicator in indicators)


def _request_with_retries(session: requests.Session, url: str) -> requests.Response | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("indeed_fetch.page_request attempt=%s/%s url=%s", attempt, MAX_RETRIES, url)
            response = session.get(url, timeout=20)
        except requests.RequestException:
            logger.exception("indeed_fetch.request_error attempt=%s url=%s", attempt, url)
            if attempt < MAX_RETRIES:
                _sleep_short_delay()
                continue
            return None

        if response.status_code == 403:
            logger.error("indeed_fetch.blocked_403 attempt=%s url=%s", attempt, url)
            if _is_block_page(response.text):
                logger.warning("Indeed blocking detected")
            if attempt < MAX_RETRIES:
                _sleep_short_delay()
                continue
            return None

        if response.status_code >= 500:
            logger.error(
                "indeed_fetch.server_error status=%s attempt=%s url=%s",
                response.status_code,
                attempt,
                url,
            )
            if attempt < MAX_RETRIES:
                _sleep_short_delay()
                continue
            return None

        if response.status_code >= 400:
            logger.error("indeed_fetch.http_error status=%s url=%s", response.status_code, url)
            return None

        if _is_block_page(response.text):
            logger.warning("Indeed blocking detected")
            return None

        return response

    return None


def fetch_jobs_indeed(target_role: str, location: Optional[str] = None, limit: int = 10) -> List[Dict[str, str]]:
    """Fetch up to `limit` jobs from Indeed search results."""
    limit = max(1, min(limit, 10))
    logger.info("indeed_fetch.start role=%s location=%s limit=%s", target_role, location, limit)

    jobs: List[Dict[str, str]] = []
    with requests.Session() as session:
        session.headers.update(DEFAULT_HEADERS)

        # Pull up to two pages to collect enough cards.
        for page_index, start in enumerate((0, 10)):
            if len(jobs) >= limit:
                break

            if page_index > 0:
                _sleep_short_delay()

            url = _build_query_url(target_role, location, start=start)
            response = _request_with_retries(session, url)
            if response is None:
                logger.error("indeed_fetch.page_failed_gracefully url=%s", url)
                # Do not crash pipeline; return what we already have or empty list.
                if not jobs:
                    return []
                break

            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.select("div.job_seen_beacon")
            logger.info("indeed_fetch.page_parsed url=%s cards=%s", url, len(cards))

            for card in cards:
                if len(jobs) >= limit:
                    break

                title_el = card.select_one("h2.jobTitle a span")
                link_el = card.select_one("h2.jobTitle a")
                company_el = card.select_one("span.companyName")
                location_el = card.select_one("div.companyLocation")
                desc_el = card.select_one("div.job-snippet")

                rel_url = link_el.get("href", "") if link_el else ""
                job_url = f"{INDEED_SITE}{rel_url}" if rel_url.startswith("/") else rel_url

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

    final_jobs = deduped[:limit]
    logger.info("indeed_fetch.success role=%s final_count=%s", target_role, len(final_jobs))
    return final_jobs
