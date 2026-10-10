"""Password hashing (bcrypt) and session tokens (JWT in an httponly cookie)."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import Settings, settings as default_settings

SESSION_COOKIE_NAME = "smartmirror_dashboard_session"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_session_token(username: str, role: str, settings: Settings = None) -> str:
    settings = settings or default_settings
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expires_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_session_token(token: str, settings: Settings = None) -> dict:
    """Raises jwt.PyJWTError (expired, bad signature, malformed) on failure."""
    settings = settings or default_settings
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
