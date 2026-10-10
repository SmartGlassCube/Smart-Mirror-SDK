"""Env-driven settings for the dashboard backend. No defaults for secrets."""

import os
import secrets


class Settings:
    def __init__(self):
        self.mongo_uri = os.getenv("DASHBOARD_MONGO_URI", "mongodb://localhost:27017/ieee?directConnection=true")
        self.mongo_db = os.getenv("DASHBOARD_MONGO_DB", "ieee")
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
