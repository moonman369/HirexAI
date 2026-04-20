"""Outreach candidate state persistence for manual LinkedIn outreach workflow."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection
from pymongo.results import UpdateResult

from app.db.client import get_collection

logger = logging.getLogger(__name__)


class OutreachCandidatesRepository:
    """Repository for outreach candidate lifecycle state."""

    def __init__(self, collection: Collection | None = None) -> None:
        self.collection = collection or get_collection("outreach_candidates")
        self.collection.create_index([("job_id", 1), ("linkedin_profile_url", 1)], unique=True)
        self.collection.create_index([("connection_status", 1), ("job_id", 1)])

    def upsert_candidate(self, candidate: dict[str, Any]) -> UpdateResult:
        now = datetime.now(timezone.utc)
        update = {
            "$set": {
                "name": candidate.get("name"),
                "company": candidate.get("company"),
                "title": candidate.get("title"),
                "linkedin_member_id": candidate.get("linkedin_member_id"),
                "updated_at": now,
            },
            "$setOnInsert": {
                "job_id": candidate["job_id"],
                "user_id": candidate["user_id"],
                "linkedin_profile_url": candidate["linkedin_profile_url"],
                "connection_status": "DISCOVERED",
                "connection_request_sent_at": None,
                "connection_accepted_at": None,
                "last_synced_at": None,
                "referral_draft": None,
                "referral_draft_approved": False,
                "referral_message_sent_at": None,
                "created_at": now,
            },
        }
        return self.collection.update_one(
            {
                "job_id": candidate["job_id"],
                "linkedin_profile_url": candidate["linkedin_profile_url"],
            },
            update,
            upsert=True,
        )

    def find_by_job(self, job_id: str) -> list[dict[str, Any]]:
        return list(self.collection.find({"job_id": job_id}))

    def find_pending_connections(self, *, job_id: str | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"connection_status": "CONNECTION_PENDING"}
        if job_id:
            query["job_id"] = job_id
        return list(self.collection.find(query))

    def find_ready_for_referral_draft(self, job_id: str) -> list[dict[str, Any]]:
        return list(
            self.collection.find(
                {
                    "job_id": job_id,
                    "connection_status": "CONNECTED",
                    "referral_draft": None,
                }
            )
        )

    def find_approved_referrals(self, job_id: str) -> list[dict[str, Any]]:
        return list(
            self.collection.find(
                {
                    "job_id": job_id,
                    "referral_draft": {"$type": "string"},
                    "referral_draft_approved": True,
                    "referral_message_sent_at": None,
                }
            )
        )

    def count_connection_requests_since(self, since: datetime) -> int:
        return int(
            self.collection.count_documents(
                {
                    "connection_request_sent_at": {"$gte": since},
                }
            )
        )

    def count_referral_messages_since(self, since: datetime) -> int:
        return int(
            self.collection.count_documents(
                {
                    "referral_message_sent_at": {"$gte": since},
                }
            )
        )

    def update_candidate_state(
        self,
        *,
        candidate_id: Any,
        connection_status: str | None = None,
        referral_draft: str | None = None,
        referral_draft_approved: bool | None = None,
        referral_message_sent_at: datetime | None = None,
        mark_connection_request_sent: bool = False,
        mark_connection_accepted: bool = False,
        mark_synced: bool = False,
    ) -> UpdateResult:
        now = datetime.now(timezone.utc)
        update_fields: dict[str, Any] = {"updated_at": now}

        if connection_status is not None:
            update_fields["connection_status"] = connection_status
        if referral_draft is not None:
            update_fields["referral_draft"] = referral_draft
        if referral_draft_approved is not None:
            update_fields["referral_draft_approved"] = referral_draft_approved
        if referral_message_sent_at is not None:
            update_fields["referral_message_sent_at"] = referral_message_sent_at
        if mark_connection_request_sent:
            update_fields["connection_request_sent_at"] = now
        if mark_connection_accepted:
            update_fields["connection_accepted_at"] = now
        if mark_synced:
            update_fields["last_synced_at"] = now

        result = self.collection.update_one({"_id": candidate_id}, {"$set": update_fields})
        logger.info(
            "db_write collection=%s action=update_candidate_state candidate_id=%s fields=%s matched=%s modified=%s",
            self.collection.name,
            candidate_id,
            sorted(update_fields.keys()),
            result.matched_count,
            result.modified_count,
        )
        return result
