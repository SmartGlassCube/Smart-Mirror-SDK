"""Pydantic models mirroring infra/mongo/CONTRACT.md (v0.3).

*In models are what the client may send -- status is a legitimate content
field (draft vs. published) and is accepted here, but created_at/updated_at/
updated_by are never accepted from the client; the server always sets them
(see routers/content.py).
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["draft", "published"]
Priority = Literal["low", "normal", "high"]
Role = Literal["admin", "editor"]


class CommonOut(BaseModel):
    id: str
    status: Status
    created_at: datetime
    updated_at: datetime
    updated_by: str


# -- events --

class EventIn(BaseModel):
    status: Status = "draft"
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    start: datetime
    end: Optional[datetime] = None
    location: Optional[str] = None
    tags: Optional[list[str]] = None
    registration_url: Optional[str] = None
    image_url: Optional[str] = None


class EventOut(EventIn, CommonOut):
    pass


# -- announcements --

class AnnouncementIn(BaseModel):
    status: Status = "draft"
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    publish_at: datetime
    expires_at: Optional[datetime] = None
    priority: Priority = "normal"


class AnnouncementOut(AnnouncementIn, CommonOut):
    pass


# -- about --

class AboutIn(BaseModel):
    status: Status = "draft"
    key: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class AboutOut(AboutIn, CommonOut):
    pass


# -- achievements --

class AchievementIn(BaseModel):
    status: Status = "draft"
    title: str = Field(min_length=1)
    date: datetime
    description: str = Field(min_length=1)


class AchievementOut(AchievementIn, CommonOut):
    pass


# -- board --

class BoardIn(BaseModel):
    status: Status = "draft"
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    term: str = Field(min_length=1)
    order: int
    email: Optional[str] = None


class BoardOut(BoardIn, CommonOut):
    pass


# -- auth --

class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    username: str
    role: Role


# -- mirror status --

class MirrorStatusOut(BaseModel):
    mirror_id: str
    last_seen: datetime
    uptime_s: float
    current_page: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None
    online: bool


# -- response envelope for writes, carries non-blocking warnings --

class WriteResult(BaseModel):
    warnings: list[str] = []
