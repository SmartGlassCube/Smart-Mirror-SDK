from .base_widget import BaseWidget


class CalendarWidget(BaseWidget):
    def __init__(self, position=None, gestures=None, content=None, data=None, data_provider=None, refresh_interval=60):
        super().__init__(
            widget_type="calendar",
            position=position,
            gestures=gestures,
            content=content,
            data=data,
            data_provider=data_provider,
            refresh_interval=refresh_interval,
        )
