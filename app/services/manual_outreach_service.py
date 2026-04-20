"""Manual, step-by-step LinkedIn outreach workflow service."""

from __future__ import annotations

import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.jobs import JobsRepository
from app.db.outreach_candidates import OutreachCandidatesRepository
from app.db.users import UsersRepository
from app.services.linkedin_client import LinkedInApiClient
from app.services.outreach_service import OutreachService

logger = logging.getLogger(__name__)

PRIORITIZED_TITLES = [
    "Software Engineer",
    "Senior Software Engineer",
    "Tech Lead",
    "Engineering Lead",
    "Hiring Manager",
    "Recruiter",
]


class ManualOutreachService:
    """Manual outreach steps (discover, connect, sync, draft, send)."""

    def __init__(
        self,
        *,
        jobs_repository: JobsRepository | None = None,
        users_repository: UsersRepository | None = None,
        outreach_candidates_repository: OutreachCandidatesRepository | None = None,
        outreach_generator: OutreachService | None = None,
        linkedin_client: LinkedInApiClient | None = None,
        max_connections_per_job: int | None = None,
        max_connections_per_week: int | None = None,
        max_messages_per_day: int | None = None,
        min_delay_seconds: int | None = None,
        max_delay_seconds: int | None = None,
    ) -> None:
        self.jobs_repository = jobs_repository or JobsRepository()
        self.users_repository = users_repository or UsersRepository()
        self.outreach_candidates_repository = outreach_candidates_repository or OutreachCandidatesRepository()
        self.outreach_generator = outreach_generator or OutreachService()
        self.linkedin_client = linkedin_client or LinkedInApiClient()

        self.max_connections_per_job = max_connections_per_job or int(os.getenv("OUTREACH_MAX_CONNECTIONS_PER_JOB", "7"))
        self.max_connections_per_week = max_connections_per_week or int(os.getenv("OUTREACH_MAX_CONNECTIONS_PER_WEEK", "100"))
        self.max_messages_per_day = max_messages_per_day or int(os.getenv("OUTREACH_MAX_MESSAGES_PER_DAY", "150"))
        self.min_delay_seconds = min_delay_seconds or int(os.getenv("OUTREACH_MIN_DELAY_SECONDS", "30"))
        self.max_delay_seconds = max_delay_seconds or int(os.getenv("OUTREACH_MAX_DELAY_SECONDS", "300"))

    def send_connection_requests(self, job_id: str) -> dict[str, Any]:
        job = self._get_job_or_raise(job_id)
        self._ensure_candidates(job)

        existing_candidates = self.outreach_candidates_repository.find_by_job(job_id)
        already_sent = [
            c
            for c in existing_candidates
            if c.get("connection_status") in {"CONNECTION_PENDING", "CONNECTED", "REFERRAL_DRAFT_READY", "REFERRAL_SENT"}
        ]

        per_job_remaining = max(0, self.max_connections_per_job - len(already_sent))
        if per_job_remaining == 0:
            return {"job_id": job_id, "requested": 0, "sent": 0, "skipped": len(existing_candidates), "reason": "per_job_limit"}

        week_start = datetime.now(timezone.utc) - timedelta(days=7)
        weekly_sent = self.outreach_candidates_repository.count_connection_requests_since(week_start)
        weekly_remaining = max(0, self.max_connections_per_week - weekly_sent)
        send_budget = min(per_job_remaining, weekly_remaining)
        if send_budget == 0:
            return {"job_id": job_id, "requested": 0, "sent": 0, "skipped": len(existing_candidates), "reason": "weekly_limit"}

        candidates = self._prioritized_candidates(existing_candidates)
        sent = 0
        skipped = 0
        for candidate in candidates:
            if sent >= send_budget:
                break

            status = candidate.get("connection_status")
            if status in {"CONNECTION_PENDING", "CONNECTED", "REFERRAL_DRAFT_READY", "REFERRAL_SENT"}:
                skipped += 1
                continue

            profile_url = candidate.get("linkedin_profile_url")
            member_id = candidate.get("linkedin_member_id")

            live_status = self.linkedin_client.get_connection_status(
                linkedin_profile_url=profile_url,
                linkedin_member_id=member_id,
            )
            mapped = self._map_connection_status(live_status)
            if mapped in {"CONNECTED", "CONNECTION_PENDING"}:
                self.outreach_candidates_repository.update_candidate_state(
                    candidate_id=candidate["_id"],
                    connection_status=mapped,
                    mark_connection_accepted=(mapped == "CONNECTED"),
                    mark_synced=True,
                )
                skipped += 1
                continue

            self._sleep_between_actions()
            note = self._build_connection_note(candidate=candidate, job=job)
            result = self.linkedin_client.send_connection_request(
                linkedin_profile_url=profile_url,
                linkedin_member_id=member_id,
                note=note,
            )
            if result.status == "RATE_LIMITED":
                logger.warning("linkedin_rate_limited action=connection_request retry_after=%s", result.retry_after_seconds)
                break
            if result.status in {"ALREADY_CONNECTED", "CONNECTED"}:
                self.outreach_candidates_repository.update_candidate_state(
                    candidate_id=candidate["_id"],
                    connection_status="CONNECTED",
                    mark_connection_accepted=True,
                    mark_synced=True,
                )
                skipped += 1
                continue
            if result.status in {"SENT", "PENDING"}:
                self.outreach_candidates_repository.update_candidate_state(
                    candidate_id=candidate["_id"],
                    connection_status="CONNECTION_PENDING",
                    mark_connection_request_sent=True,
                    mark_synced=True,
                )
                sent += 1
                continue

            skipped += 1

        return {"job_id": job_id, "requested": send_budget, "sent": sent, "skipped": skipped}

    def sync_connection_statuses(self, job_id: str | None = None) -> dict[str, Any]:
        pending = self.outreach_candidates_repository.find_pending_connections(job_id=job_id)
        connected = 0
        still_pending = 0
        rejected_or_expired = 0

        for candidate in pending:
            live_status = self.linkedin_client.get_connection_status(
                linkedin_profile_url=candidate["linkedin_profile_url"],
                linkedin_member_id=candidate.get("linkedin_member_id"),
            )
            mapped = self._map_connection_status(live_status)
            if mapped == "CONNECTED":
                connected += 1
            elif mapped == "CONNECTION_PENDING":
                still_pending += 1
            else:
                rejected_or_expired += 1

            self.outreach_candidates_repository.update_candidate_state(
                candidate_id=candidate["_id"],
                connection_status=mapped,
                mark_connection_accepted=(mapped == "CONNECTED"),
                mark_synced=True,
            )

        return {
            "job_id": job_id,
            "inspected": len(pending),
            "connected": connected,
            "pending": still_pending,
            "rejected_or_expired": rejected_or_expired,
        }

    def generate_referral_drafts(self, job_id: str) -> dict[str, Any]:
        job = self._get_job_or_raise(job_id)
        user_resume = self.users_repository.get_resume_text(job["user_id"]) or ""
        candidates = self.outreach_candidates_repository.find_ready_for_referral_draft(job_id)

        generated = 0
        for candidate in candidates:
            highlights = self._resume_highlights(job=job, user_resume=user_resume)
            enriched_jd = f"{job.get('jd_text', '')}\n\nContact title: {candidate.get('title') or ''}"
            draft = self.outreach_generator.generate_referral_message(
                jd_text=enriched_jd,
                resume_highlights=highlights,
            )
            self.outreach_candidates_repository.update_candidate_state(
                candidate_id=candidate["_id"],
                connection_status="REFERRAL_DRAFT_READY",
                referral_draft=self._personalize_draft(draft, candidate),
            )
            generated += 1

        return {"job_id": job_id, "generated": generated}

    def send_approved_referral_messages(self, job_id: str) -> dict[str, Any]:
        day_start = datetime.now(timezone.utc) - timedelta(days=1)
        messages_today = self.outreach_candidates_repository.count_referral_messages_since(day_start)
        daily_remaining = max(0, self.max_messages_per_day - messages_today)

        candidates = self.outreach_candidates_repository.find_approved_referrals(job_id)
        sent = 0
        skipped = 0

        for candidate in candidates:
            if sent >= daily_remaining:
                break
            if candidate.get("connection_status") not in {"CONNECTED", "REFERRAL_DRAFT_READY"}:
                skipped += 1
                continue

            self._sleep_between_actions()
            result = self.linkedin_client.send_message(
                linkedin_profile_url=candidate["linkedin_profile_url"],
                linkedin_member_id=candidate.get("linkedin_member_id"),
                message=candidate["referral_draft"],
            )
            if result.status == "RATE_LIMITED":
                logger.warning("linkedin_rate_limited action=send_message retry_after=%s", result.retry_after_seconds)
                break
            if result.status != "SENT":
                skipped += 1
                continue

            self.outreach_candidates_repository.update_candidate_state(
                candidate_id=candidate["_id"],
                connection_status="REFERRAL_SENT",
                referral_message_sent_at=datetime.now(timezone.utc),
            )
            sent += 1

        return {"job_id": job_id, "sent": sent, "skipped": skipped, "daily_remaining": daily_remaining}

    def _ensure_candidates(self, job: dict[str, Any]) -> None:
        existing = self.outreach_candidates_repository.find_by_job(job["job_id"])
        if existing:
            return

        candidates = self.linkedin_client.discover_candidates(
            job_text=job.get("jd_text") or "",
            titles=PRIORITIZED_TITLES,
            limit=self.max_connections_per_job,
        )
        for candidate in candidates:
            self.outreach_candidates_repository.upsert_candidate(
                {
                    "job_id": job["job_id"],
                    "user_id": job["user_id"],
                    "linkedin_profile_url": candidate.linkedin_profile_url,
                    "linkedin_member_id": candidate.linkedin_member_id,
                    "name": candidate.name,
                    "company": candidate.company,
                    "title": candidate.title,
                }
            )

    def _get_job_or_raise(self, job_id: str) -> dict[str, Any]:
        job = self.jobs_repository.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        return job

    def _prioritized_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        priority = {title.lower(): idx for idx, title in enumerate(PRIORITIZED_TITLES)}

        def key(candidate: dict[str, Any]) -> tuple[int, str]:
            candidate_title = str(candidate.get("title") or "").lower()
            rank = len(priority)
            for title, idx in priority.items():
                if title in candidate_title:
                    rank = idx
                    break
            return rank, str(candidate.get("name") or "")

        return sorted(candidates, key=key)

    def _map_connection_status(self, value: str) -> str:
        normalized = (value or "").upper()
        if normalized in {"CONNECTED", "ALREADY_CONNECTED"}:
            return "CONNECTED"
        if normalized in {"PENDING", "CONNECTION_PENDING", "INVITED"}:
            return "CONNECTION_PENDING"
        if normalized in {"REJECTED"}:
            return "CONNECTION_REJECTED"
        if normalized in {"EXPIRED", "WITHDRAWN"}:
            return "CONNECTION_EXPIRED"
        return "CONNECTION_PENDING"

    def _build_connection_note(self, *, candidate: dict[str, Any], job: dict[str, Any]) -> str:
        name = (candidate.get("name") or "there").split(" ")[0]
        return (
            f"Hi {name}, I came across a role at {candidate.get('company') or 'your company'} and would love to connect. "
            "I think my background aligns with the team and would value your perspective."
        )[:280]

    def _resume_highlights(self, *, job: dict[str, Any], user_resume: str) -> list[str]:
        strengths = job.get("strengths") or []
        if strengths:
            return [str(item) for item in strengths[:4]]

        if not user_resume.strip():
            return ["Experience aligned with backend and product engineering roles."]

        snippets = [part.strip() for part in user_resume.split("\n") if part.strip()]
        return snippets[:4] or ["Experience aligned with backend and product engineering roles."]

    def _personalize_draft(self, draft: str, candidate: dict[str, Any]) -> str:
        first_name = (candidate.get("name") or "there").split(" ")[0]
        return f"Hi {first_name},\n\n{draft}".strip()

    def _sleep_between_actions(self) -> None:
        low = min(self.min_delay_seconds, self.max_delay_seconds)
        high = max(self.min_delay_seconds, self.max_delay_seconds)
        if high <= 0:
            return
        delay = random.randint(low, high)
        time.sleep(delay)
