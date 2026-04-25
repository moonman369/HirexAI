from __future__ import annotations

from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from app.config import settings


_client: MongoClient[Any] | None = None
_db: Database[Any] | None = None


def get_client() -> MongoClient[Any]:
    global _client
    if _client is None:
        _client = MongoClient(settings.mongodb_uri)
    return _client


def get_database() -> Database[Any]:
    global _db
    if _db is None:
        _db = get_client()[settings.mongodb_db_name]
    return _db


def get_collection(name: str) -> Collection[Any]:
    return get_database()[name]


def init_indexes() -> None:
    users = get_collection("users")
    profiles = get_collection("profiles")
    job_runs = get_collection("job_runs")

    users.create_index("email", unique=True)
    profiles.create_index("user_id", unique=True)
    job_runs.create_index([("user_id", 1), ("created_at", -1)])
