#!/usr/bin/env python
"""Create (or reset the password of) an admin user in dashboard_users.

Usage:
    uv run python scripts/create_admin.py <username> <password> [--role editor]
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.db import get_db
from app.security import hash_password


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("--role", choices=["admin", "editor"], default="admin")
    args = parser.parse_args()

    db = get_db(settings)
    now = datetime.now(timezone.utc)
    db.dashboard_users.update_one(
        {"username": args.username},
        {"$set": {
            "username": args.username,
            "password_hash": hash_password(args.password),
            "role": args.role,
            "updated_at": now,
        }, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    print(f"ok: {args.role} user {args.username!r} ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
