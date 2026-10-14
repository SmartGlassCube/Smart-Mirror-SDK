#!/usr/bin/env python
"""Idempotent admin bootstrap, meant to be called by ./dev.sh on every `up`.

- Creates the configured admin user if they don't exist yet.
- Never touches the password of an existing user unless --sync-password
  is passed (so re-running `up` doesn't silently change a password someone
  rotated by hand).
- Deletes the overnight-session throwaway admin/supersecret123 dev
  credential, unless that IS the configured username (then the logic
  above handles it normally).

Usage:
    uv run python scripts/bootstrap_admin.py <username> <password> [--sync-password]
Never prints the password.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.db import get_db
from app.security import hash_password, verify_password

THROWAWAY_USERNAME = "admin"
THROWAWAY_PASSWORD = "supersecret123"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("--sync-password", action="store_true")
    args = parser.parse_args()

    db = get_db(settings)
    now = datetime.now(timezone.utc)

    existing = db.dashboard_users.find_one({"username": args.username})

    # The account we're bootstrapping might itself still be carrying the
    # known throwaway password -- this happens whenever DASHBOARD_ADMIN_USER
    # is "admin" (the throwaway credential's own username). There's no real
    # secret to protect there, so replace it even without --sync-password.
    if existing is not None and verify_password(THROWAWAY_PASSWORD, existing["password_hash"]):
        db.dashboard_users.update_one(
            {"_id": existing["_id"]},
            {"$set": {"password_hash": hash_password(args.password), "role": "admin", "updated_at": now}},
        )
        print(f"replaced known throwaway password for {args.username!r}")
        return 0

    # Otherwise, a differently-named throwaway admin/supersecret123 user is
    # just clutter from an earlier session -- remove it.
    if THROWAWAY_USERNAME != args.username:
        throwaway = db.dashboard_users.find_one({"username": THROWAWAY_USERNAME})
        if throwaway and verify_password(THROWAWAY_PASSWORD, throwaway["password_hash"]):
            db.dashboard_users.delete_one({"_id": throwaway["_id"]})
            print(f"removed throwaway dev user {THROWAWAY_USERNAME!r}")

    if existing is None:
        db.dashboard_users.insert_one({
            "username": args.username,
            "password_hash": hash_password(args.password),
            "role": "admin",
            "created_at": now,
            "updated_at": now,
        })
        print(f"created admin user {args.username!r}")
    elif args.sync_password:
        db.dashboard_users.update_one(
            {"_id": existing["_id"]},
            {"$set": {"password_hash": hash_password(args.password), "updated_at": now}},
        )
        print(f"synced password for {args.username!r} from .env")
    else:
        print(f"user {args.username!r} already exists, left untouched (pass --sync-password to overwrite)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
