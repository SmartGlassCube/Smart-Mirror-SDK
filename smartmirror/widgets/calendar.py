from .base import BaseWidget


class CalendarWidget(BaseWidget):
    """Month view plus upcoming events. Expects `data = {"events": [{"title", "start", "location"}]}`."""

    type = "calendar"
    refresh_interval = 60
