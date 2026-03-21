from .base_widget import BaseWidget


class WeatherWidget(BaseWidget):
    def __init__(self, position=None, gestures=None, content=None, data=None, data_provider=None, refresh_interval=300):
        super().__init__(
            widget_type="weather",
            position=position,
            gestures=gestures,
            content=content,
            data=data,
            data_provider=data_provider,
            refresh_interval=refresh_interval,
        )
