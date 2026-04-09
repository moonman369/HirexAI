"""Jobs collection data access helpers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection
from pymongo.results import InsertManyResult, UpdateResult

from app.db.client import get_collection

logger = logging.getLogger(__name__)


class JobsRepository:
    """Repository for operations on the jobs collection."""

    def __init__(self, collection: Collection | None = None) -> None:
        self.collection = collection or get_collection("jobs")

    def insert_jobs(self, jobs: list[dict[str, Any]]) -> InsertManyResult | None:
        """Insert a batch of jobs into the jobs collection."""
        if not jobs:
            return None

        now = datetime.now(timezone.utc)
        payload = []
        for job in jobs:
            job_doc = {
                **job,
                "created_at": job.get("created_at", now),
                "updated_at": now,
            }
            payload.append(job_doc)

        result = self.collection.insert_many(payload)
        job_ids = [job.get("job_id") for job in payload]
        logger.info(
            "db_write collection=%s action=insert_jobs inserted=%s job_ids=%s",
            self.collection.name,
            len(result.inserted_ids),
            job_ids,
        )
        return result

    def update_job_processing(
        self,
        job_id: str,
        *,
        jd_text: str | None = None,
        match_score: float | None = None,
        status: str | None = None,
    ) -> UpdateResult:
        """Update job processing fields for a job."""
        update_fields: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
        if jd_text is not None:
            update_fields["jd_text"] = jd_text
        if match_score is not None:
            update_fields["match_score"] = match_score
        if status is not None:
            update_fields["status"] = status

        result = self.collection.update_one({"job_id": job_id}, {"$set": update_fields})
        logger.info(
            "db_write collection=%s action=update_job_processing job_id=%s fields=%s matched=%s modified=%s",
            self.collection.name,
            job_id,
            sorted(update_fields.keys()),
            result.matched_count,
            result.modified_count,
        )
        return result
