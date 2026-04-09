"""Outreach collection data access helpers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection
from pymongo.results import InsertOneResult

from app.db.client import get_collection

logger = logging.getLogger(__name__)


class OutreachRepository:
    """Repository for operations on the outreach collection."""

    def __init__(self, collection: Collection | None = None) -> None:
        self.collection = collection or get_collection("outreach")

    def store_outreach_message(
        self,
        *,
        job_id: str,
        user_id: str,
        message: str,
        channel: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> InsertOneResult:
        """Store an outreach message tied to a job."""
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "job_id": job_id,
            "user_id": user_id,
            "message": message,
            "channel": channel,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        result = self.collection.insert_one(payload)
        logger.info(
            "db_write collection=%s action=store_outreach_message job_id=%s user_id=%s inserted_id=%s",
            self.collection.name,
            job_id,
            user_id,
            result.inserted_id,
        )
        return result
