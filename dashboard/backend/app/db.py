"""The one Mongo connection the dashboard process holds."""

from functools import lru_cache

from fastapi import Depends
from pymongo import MongoClient
from pymongo.database import Database
from typing_extensions import Annotated

from .config import Settings, settings as default_settings


@lru_cache
def _client(mongo_uri: str) -> MongoClient:
    return MongoClient(mongo_uri, tz_aware=True)


def get_settings() -> Settings:
    return default_settings


def get_db(settings: Annotated[Settings, Depends(get_settings)] = None) -> Database:
    """FastAPI dependency (no-arg call sites, e.g. scripts/create_admin.py, pass settings explicitly)."""
    settings = settings or default_settings
    return _client(settings.mongo_uri)[settings.mongo_db]
