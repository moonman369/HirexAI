"""Scraping service with Playwright-based HTML retrieval and text extraction."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ScrapeResult:
    """Structured result from a scrape call."""

    text: str
    raw_html: str


HtmlFetcher = Callable[[str], str]
TextExtractor = Callable[[str], str]


def playwright_fetch_html(url: str, *, timeout_ms: int = 30_000, wait_until: str = "domcontentloaded") -> str:
    """Fetch a page's HTML using Playwright.

    Import is intentionally lazy so the service can still be imported when
    Playwright is not installed.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("Playwright is required for playwright_fetch_html") from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until=wait_until, timeout=timeout_ms)
        html = page.content()
        browser.close()
        return html


def basic_html_to_text(raw_html: str) -> str:
    """Convert HTML to plain text using a lightweight, dependency-free strategy."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", raw_html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class ScraperService:
    """Service that scrapes and extracts job description text from URLs."""

    def __init__(
        self,
        *,
        html_fetcher: HtmlFetcher = playwright_fetch_html,
        text_extractor: TextExtractor = basic_html_to_text,
        failure_log_chars: int = 4_000,
    ) -> None:
        self.html_fetcher = html_fetcher
        self.text_extractor = text_extractor
        self.failure_log_chars = failure_log_chars

    def scrape(self, *, job_id: str, user_id: str, url: str) -> str:
        """Protocol-compatible scrape entrypoint returning extracted text."""
        result = self.scrape_with_raw_html(job_id=job_id, user_id=user_id, url=url)
        return result.text

    def scrape_with_raw_html(self, *, job_id: str, user_id: str, url: str) -> ScrapeResult:
        """Return extracted text and source HTML for downstream debugging."""
        raw_html = self.html_fetcher(url)

        try:
            text = self.text_extractor(raw_html)
            if not text:
                raise ValueError("text extractor returned empty output")
            return ScrapeResult(text=text, raw_html=raw_html)
        except Exception:
            self._log_extraction_failure(job_id=job_id, user_id=user_id, url=url, raw_html=raw_html)
            raise

    def _log_extraction_failure(self, *, job_id: str, user_id: str, url: str, raw_html: str) -> None:
        logger.error(
            "scrape_extraction_failed job_id=%s user_id=%s url=%s raw_html_snippet=%r",
            job_id,
            user_id,
            url,
            raw_html[: self.failure_log_chars],
        )
