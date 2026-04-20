"""Lightweight LinkedIn API adapter for manual outreach steps."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class LinkedInCandidate:
    linkedin_profile_url: str
    linkedin_member_id: str | None
    name: str | None
    company: str | None
    title: str | None


@dataclass(slots=True)
class LinkedInActionResult:
    status: str
    retry_after_seconds: int | None = None


class LinkedInApiClient:
    """Minimal HTTP client for external LinkedIn-compatible API wrappers."""

    def __init__(self, *, base_url: str | None = None, token: str | None = None, timeout_seconds: int = 30) -> None:
        self.base_url = (base_url or os.getenv("LINKEDIN_API_BASE_URL") or "").rstrip("/")
        self.token = token or os.getenv("LINKEDIN_API_TOKEN")
        self.timeout_seconds = timeout_seconds

    def _require_config(self) -> None:
        if not self.base_url or not self.token:
            raise RuntimeError("LinkedIn API is not configured. Set LINKEDIN_API_BASE_URL and LINKEDIN_API_TOKEN")

    def _request(self, *, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any], dict[str, str]]:
        self._require_config()
        url = f"{self.base_url}{path}"
        body = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(url=url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                status = response.status
                response_headers = {k.lower(): v for k, v in response.headers.items()}
                raw = response.read().decode("utf-8")
                parsed = json.loads(raw) if raw else {}
                return status, parsed, response_headers
        except urllib.error.HTTPError as err:
            raw = err.read().decode("utf-8") if err.fp else ""
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"error": raw}
            headers_out = {k.lower(): v for k, v in err.headers.items()} if err.headers else {}
            return err.code, parsed, headers_out

    def discover_candidates(self, *, job_text: str, titles: list[str], limit: int) -> list[LinkedInCandidate]:
        payload = {"job_text": job_text, "titles": titles, "limit": limit}
        status, response, _ = self._request(method="POST", path="/candidates/discover", payload=payload)
        if status >= 400:
            return []
        candidates: list[LinkedInCandidate] = []
        for item in response.get("candidates", []):
            profile_url = str(item.get("linkedin_profile_url") or "").strip()
            if not profile_url:
                continue
            candidates.append(
                LinkedInCandidate(
                    linkedin_profile_url=profile_url,
                    linkedin_member_id=item.get("linkedin_member_id"),
                    name=item.get("name"),
                    company=item.get("company"),
                    title=item.get("title"),
                )
            )
        return candidates

    def get_connection_status(self, *, linkedin_profile_url: str, linkedin_member_id: str | None = None) -> str:
        query = urllib.parse.urlencode(
            {
                "linkedin_profile_url": linkedin_profile_url,
                "linkedin_member_id": linkedin_member_id or "",
            }
        )
        status, response, _ = self._request(method="GET", path=f"/connections/status?{query}")
        if status >= 400:
            return "PENDING"
        return str(response.get("status") or "PENDING").upper()

    def send_connection_request(
        self,
        *,
        linkedin_profile_url: str,
        linkedin_member_id: str | None,
        note: str | None,
    ) -> LinkedInActionResult:
        payload = {
            "linkedin_profile_url": linkedin_profile_url,
            "linkedin_member_id": linkedin_member_id,
            "note": note,
        }
        status, response, headers = self._request(method="POST", path="/connections", payload=payload)
        if status == 429:
            return LinkedInActionResult(
                status="RATE_LIMITED",
                retry_after_seconds=int(headers.get("retry-after", "60")),
            )
        if status >= 400:
            return LinkedInActionResult(status="FAILED")
        return LinkedInActionResult(status=str(response.get("status") or "SENT").upper())

    def send_message(
        self,
        *,
        linkedin_profile_url: str,
        linkedin_member_id: str | None,
        message: str,
    ) -> LinkedInActionResult:
        payload = {
            "linkedin_profile_url": linkedin_profile_url,
            "linkedin_member_id": linkedin_member_id,
            "message": message,
        }
        status, response, headers = self._request(method="POST", path="/messages", payload=payload)
        if status == 429:
            return LinkedInActionResult(
                status="RATE_LIMITED",
                retry_after_seconds=int(headers.get("retry-after", "60")),
            )
        if status >= 400:
            return LinkedInActionResult(status="FAILED")
        return LinkedInActionResult(status=str(response.get("status") or "SENT").upper())
