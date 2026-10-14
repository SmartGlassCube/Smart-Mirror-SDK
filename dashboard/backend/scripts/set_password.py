#!/usr/bin/env python
"""Used by `./dev.sh reset-password`: always overwrite a password, preserving
an existing user's role (create them as admin if they don't exist).

Usage: uv run python scripts/set_password.py <username> <password>
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.db import get_db
from app.security import hash_password


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: set_password.py <username> <password>", file=sys.stderr)
        return 2
    username, password = sys.argv[1], sys.argv[2]

    db = get_db(settings)
    now = datetime.now(timezone.utc)
    existing = db.dashboard_users.find_one({"username": username})
    if existing is None:
        db.dashboard_users.insert_one({
            "username": username,
            "password_hash": hash_password(password),
            "role": "admin",
            "created_at": now,
            "updated_at": now,
        })
        print(f"created admin user {username!r}")
    else:
        db.dashboard_users.update_one(
            {"_id": existing["_id"]}, {"$set": {"password_hash": hash_password(password), "updated_at": now}}
        )
        print(f"password updated for {username!r} (role unchanged: {existing['role']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
