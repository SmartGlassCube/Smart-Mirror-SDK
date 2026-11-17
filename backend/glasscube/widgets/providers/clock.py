from datetime import datetime, timezone


class ClockProvider:
    """The local time, for clock widgets: `{"time": "14:05", "seconds": "07", "date": "Tuesday 17 November", "iso"}`.

    `hour12=True` gives "2:05 PM". Give the widget `refresh_interval=1` so the seconds tick.
    Same shape as Smart Mirror Studio's clock data source.
    """

    def __init__(self, hour12=False):
        self.hour12 = hour12

    def __call__(self, _widget=None, now=None):
        now = now or datetime.now()
        if self.hour12:
            hour = (now.hour + 11) % 12 + 1
            time = f"{hour}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'}"
        else:
            time = f"{now.hour:02d}:{now.minute:02d}"
        return {
            "time": time,
            "seconds": f"{now.second:02d}",
            "date": f"{now:%A} {now.day} {now:%B}",
            "iso": now.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        }
