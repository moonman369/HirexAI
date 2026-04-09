"""Users collection data access helpers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection
from pymongo.results import UpdateResult

from app.db.client import get_collection

logger = logging.getLogger(__name__)


class UsersRepository:
    """Repository for operations on the users collection."""

    def __init__(self, collection: Collection | None = None) -> None:
        self.collection = collection or get_collection("users")

    def upsert_user_resume(
        self,
        user_id: str,
        resume_text: str,
        resume_metadata: dict[str, Any] | None = None,
    ) -> UpdateResult:
        """Create or update a user's resume payload."""
        now = datetime.now(timezone.utc)
        result = self.collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "resume_text": resume_text,
                    "resume_metadata": resume_metadata or {},
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "created_at": now,
                },
            },
            upsert=True,
        )
        logger.info(
            "db_write collection=%s action=upsert_user_resume user_id=%s matched=%s modified=%s upserted_id=%s",
            self.collection.name,
            user_id,
            result.matched_count,
            result.modified_count,
            result.upserted_id,
        )
        return result

    def get_resume_text(self, user_id: str) -> str | None:
        """Return stored resume text for a user when available."""
        document = self.collection.find_one({"user_id": user_id}, {"resume_text": 1, "_id": 0})
        if not document:
            return None
        resume_text = document.get("resume_text")
        if isinstance(resume_text, str) and resume_text.strip():
            return resume_text
        return None
