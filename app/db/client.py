"""Mongo client factory and collection access helpers."""

from __future__ import annotations

import os
from functools import lru_cache

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

DEFAULT_DB_NAME = "hirexai"


def _required_env(name: str, *, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _mongo_uri() -> str:
    return _required_env("MONGO_URI")


def _mongo_db_name() -> str:
    return _required_env("MONGO_DB", default=DEFAULT_DB_NAME)


@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient:
    """Return a cached MongoDB client configured from environment variables."""
    return MongoClient(_mongo_uri())


@lru_cache(maxsize=1)
def get_database() -> Database:
    """Return the configured Mongo database."""
    return get_mongo_client()[_mongo_db_name()]


def get_collection(name: str) -> Collection:
    """Return a collection from the configured database."""
    return get_database()[name]
