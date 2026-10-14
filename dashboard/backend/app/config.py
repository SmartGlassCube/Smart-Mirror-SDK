"""Env-driven settings for the dashboard backend. No defaults for secrets.

Env source of truth: the repo-root `.env` (managed by `./dev.sh`), holding
MONGO_URI / DASHBOARD_ADMIN_* / DASHBOARD_JWT_SECRET -- shared with the
mirror's own MONGO_URI switch (smartmirror.content.config). It's loaded
here too (not just inherited from dev.sh's shell) so the backend also
works standalone (e.g. `uv run uvicorn app.main:app` without dev.sh).
dashboard/backend/.env, if present, is a secondary per-service override
for anyone who'd rather not touch the root file -- loaded first, then the
root file loads on top of it with override=True, so root always wins.
The legacy DASHBOARD_MONGO_URI / DASHBOARD_MONGO_DB names are still read as
a fallback if MONGO_URI / MONGO_DB aren't set.
"""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ROOT_DIR = _BACKEND_DIR.parent.parent

load_dotenv(_BACKEND_DIR / ".env")
load_dotenv(_ROOT_DIR / ".env", override=True)


class Settings:
    def __init__(self):
        self.mongo_uri = (
            os.getenv("MONGO_URI")
            or os.getenv("DASHBOARD_MONGO_URI")
            or "mongodb://localhost:27017/ieee?directConnection=true"
        )
        self.mongo_db = os.getenv("MONGO_DB") or os.getenv("DASHBOARD_MONGO_DB") or "ieee"
        # No safe default for a real deployment -- falls back to a random
        # per-process secret (fine for dev/tests, logs everyone out on
        # restart) but DASHBOARD_JWT_SECRET should be set for anything real.
        self.jwt_secret = os.getenv("DASHBOARD_JWT_SECRET") or secrets.token_urlsafe(32)
        self.jwt_algorithm = "HS256"
        self.jwt_expires_minutes = int(os.getenv("DASHBOARD_JWT_EXPIRES_MINUTES", "480"))
        self.cors_origins = [
            origin.strip()
            for origin in os.getenv("DASHBOARD_CORS_ORIGINS", "http://localhost:5174").split(",")
            if origin.strip()
        ]
        self.cookie_secure = os.getenv("DASHBOARD_COOKIE_SECURE", "false").lower() == "true"


def load_settings() -> Settings:
    return Settings()


settings = load_settings()
