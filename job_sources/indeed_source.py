from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Dict, List, Optional
from urllib.parse import quote_plus

if TYPE_CHECKING:
    from playwright.sync_api import Locator


INDEED_SITE = "https://in.indeed.com"
INDEED_BASE = f"{INDEED_SITE}/jobs"
logger = logging.getLogger(__name__)


def _build_query_url(target_role: str, location: Optional[str]) -> str:
    query = quote_plus(target_role)
    loc = quote_plus(location or "")
    return f"{INDEED_BASE}?q={query}&l={loc}"


def _first_text(card: "Locator", selector: str) -> str:
    loc = card.locator(selector).first
    if loc.count() == 0:
        return ""
    return loc.text_content() or ""


def _first_attr(card: "Locator", selector: str, attr_name: str) -> str:
    loc = card.locator(selector).first
    if loc.count() == 0:
        return ""
    return loc.get_attribute(attr_name) or ""


def fetch_jobs_indeed(target_role: str, location: Optional[str] = None, limit: int = 10) -> List[Dict[str, str]]:
    """Fetch up to `limit` jobs from Indeed using Playwright."""
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.exception("indeed_playwright_fetch.import_failed")
        return []

    limit = max(1, min(limit, 10))
    url = _build_query_url(target_role, location)
    logger.info("indeed_playwright_fetch.start role=%s location=%s limit=%s", target_role, location, limit)

    jobs: List[Dict[str, str]] = []

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 768},
                locale="en-US",
                timezone_id="Asia/Kolkata",
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(int(random.uniform(1, 3) * 1000))
                page.wait_for_selector("div.job_seen_beacon", timeout=10000)

                cards = page.locator("div.job_seen_beacon")
                card_count = min(cards.count(), limit)
                logger.info("indeed_playwright_fetch.cards_found count=%s url=%s", card_count, url)

                for idx in range(card_count):
                    card = cards.nth(idx)

                    title = _first_text(card, "h2.jobTitle span[title]") or _first_text(card, "h2.jobTitle a span")
                    company = _first_text(card, "span[data-testid='company-name']") or _first_text(card, "span.companyName")
                    job_location = _first_text(card, "div[data-testid='text-location']") or _first_text(card, "div.companyLocation")
                    job_description = _first_text(card, "div.job-snippet") or _first_text(card, "ul")

                    rel_url = _first_attr(card, "h2.jobTitle a", "href")
                    job_url = f"{INDEED_SITE}{rel_url}" if rel_url.startswith("/") else rel_url

                    jobs.append(
                        {
                            "title": " ".join((title or "").split()) or "Unknown Title",
                            "company": " ".join((company or "").split()) or "Unknown Company",
                            "location": " ".join((job_location or "").split()) or "Unknown Location",
                            "job_url": job_url,
                            "job_description": " ".join((job_description or "").split()),
                        }
                    )
            finally:
                context.close()
                browser.close()

    except PlaywrightTimeoutError:
        logger.exception("indeed_playwright_fetch.timeout url=%s", url)
        return []
    except Exception:
        logger.exception("indeed_playwright_fetch.failed url=%s", url)
        return []

    seen = set()
    deduped: List[Dict[str, str]] = []
    for job in jobs:
        key = job["job_url"] or f"{job['title']}::{job['company']}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)

    final_jobs = deduped[:limit]
    logger.info("indeed_playwright_fetch.success role=%s final_count=%s", target_role, len(final_jobs))
    return final_jobs
