"""Login/logout + the get_current_user dependency every content endpoint requires."""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pymongo.database import Database
import jwt

from .config import settings
from .db import get_db
from .models import LoginIn, Role, UserOut
from .security import SESSION_COOKIE_NAME, create_session_token, decode_session_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class CurrentUser(UserOut):
    pass


def get_current_user(session: str = Cookie(default=None, alias=SESSION_COOKIE_NAME)) -> CurrentUser:
    if session is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_session_token(session)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return CurrentUser(username=payload["sub"], role=payload["role"])


def require_role(*roles: Role):
    def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Not authorized")
        return user
    return _check


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response, db: Database = Depends(get_db)):
    user_doc = db.dashboard_users.find_one({"username": body.username})
    if user_doc is None or not verify_password(body.password, user_doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_session_token(user_doc["username"], user_doc["role"])
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_expires_minutes * 60,
    )
    return UserOut(username=user_doc["username"], role=user_doc["role"])


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser = Depends(get_current_user)):
    return user
