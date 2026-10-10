from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pymongo.database import Database

from ..auth import CurrentUser, get_current_user
from ..db import get_db
from ..models import MirrorStatusOut

ONLINE_THRESHOLD_SECONDS = 90

router = APIRouter(prefix="/api/mirror", tags=["mirror"])


@router.get("/status", response_model=list[MirrorStatusOut])
def mirror_status(db: Database = Depends(get_db), _user: CurrentUser = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    out = []
    for doc in db.mirror_status.find({}):
        last_seen = doc["last_seen"]
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        online = now - last_seen < timedelta(seconds=ONLINE_THRESHOLD_SECONDS)
        out.append({**doc, "online": online})
    return out
