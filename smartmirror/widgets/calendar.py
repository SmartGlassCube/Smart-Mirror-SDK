from .base import BaseWidget


class CalendarWidget(BaseWidget):
    """Month view plus the events of today (or the next day with some).

    Expects `data = {"days": {"2026-10-28": [{"title", "start", "location", "chapter_name"}]}}`
    (events keyed by local day, see ContentSync.calendar_days), or a flat
    `{"events": [{"title", "start", "location"}]}` the frontend groups by day itself.
    """

    type = "calendar"
    refresh_interval = 60
