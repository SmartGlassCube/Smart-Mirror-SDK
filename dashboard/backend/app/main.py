from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import router as auth_router
from .config import settings
from .models import (
    AboutIn, AboutOut, AchievementIn, AchievementOut, AnnouncementIn, AnnouncementOut,
    BoardIn, BoardOut, EventIn, EventOut,
)
from .routers.content import make_content_router
from .routers.mirror import router as mirror_router

app = FastAPI(title="Smart Mirror Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(mirror_router)
app.include_router(make_content_router("events", EventIn, EventOut, long_text_fields=("description",)))
app.include_router(make_content_router("announcements", AnnouncementIn, AnnouncementOut, long_text_fields=("body",)))
app.include_router(make_content_router("about", AboutIn, AboutOut, long_text_fields=("body",)))
app.include_router(make_content_router("achievements", AchievementIn, AchievementOut, long_text_fields=("description",)))
app.include_router(make_content_router("board", BoardIn, BoardOut))


@app.get("/api/health")
def health():
    return {"ok": True}
