import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB = "ieee_dashboard_test"
os.environ["DASHBOARD_MONGO_URI"] = "mongodb://localhost:27017/?directConnection=true"
os.environ["DASHBOARD_MONGO_DB"] = TEST_DB
os.environ["DASHBOARD_JWT_SECRET"] = "test-secret-at-least-32-bytes-long-for-hs256"

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.config import Settings
from app.db import get_db
from app.main import app
from app.security import hash_password

MONGO_URI = "mongodb://localhost:27017/?directConnection=true"


def _mongo_reachable() -> bool:
    try:
        MongoClient(MONGO_URI, serverSelectionTimeoutMS=1000).admin.command("ping")
        return True
    except PyMongoError:
        return False


requires_mongo = pytest.mark.skipif(
    not _mongo_reachable(),
    reason="local Mongo not reachable at mongodb://localhost:27017 -- start it with infra/mongo/dev_mongod.sh start",
)


@pytest.fixture
def db():
    client = MongoClient(MONGO_URI, tz_aware=True)
    database = client[TEST_DB]
    for name in database.list_collection_names():
        database.drop_collection(name)

    str_schema = {"bsonType": "string", "minLength": 1}
    date_schema = {"bsonType": "date"}
    common = {
        "status": {"enum": ["draft", "published"]},
        "created_at": date_schema,
        "updated_at": date_schema,
        "updated_by": str_schema,
    }
    common_req = ["status", "created_at", "updated_at", "updated_by"]

    def ensure(name, props, required):
        database.create_collection(name, validator={"$jsonSchema": {
            "bsonType": "object", "required": common_req + required, "properties": {**common, **props},
        }}, validationLevel="strict", validationAction="error")

    ensure("events", {"title": str_schema, "description": str_schema, "start": date_schema, "end": date_schema},
           ["title", "description", "start"])
    ensure("announcements", {
        "title": str_schema, "body": str_schema, "publish_at": date_schema, "expires_at": date_schema,
        "priority": {"enum": ["low", "normal", "high"]},
    }, ["title", "body", "publish_at", "priority"])
    ensure("about", {"key": str_schema, "title": str_schema, "body": str_schema}, ["key", "title", "body"])
    ensure("achievements", {"title": str_schema, "date": date_schema, "description": str_schema},
           ["title", "date", "description"])
    ensure("board", {"name": str_schema, "role": str_schema, "term": str_schema, "order": {"bsonType": "int"}},
           ["name", "role", "term", "order"])
    database.create_collection("mirror_status")
    database.create_collection("audit_log")

    yield database

    client.drop_database(TEST_DB)
    client.close()


@pytest.fixture
def client(db):
    def _get_db_override():
        return db

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    db.dashboard_users.insert_one({
        "username": "admin", "password_hash": hash_password("adminpass123"),
        "role": "admin", "created_at": now, "updated_at": now,
    })
    return {"username": "admin", "password": "adminpass123"}


@pytest.fixture
def editor_user(db):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    db.dashboard_users.insert_one({
        "username": "editor", "password_hash": hash_password("editorpass123"),
        "role": "editor", "created_at": now, "updated_at": now,
    })
    return {"username": "editor", "password": "editorpass123"}


@pytest.fixture
def logged_in_client(client, admin_user):
    resp = client.post("/api/auth/login", json=admin_user)
    assert resp.status_code == 200
    return client
