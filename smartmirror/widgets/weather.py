from .base import BaseWidget


class WeatherWidget(BaseWidget):
    """Current weather card.

    Give it an `OpenMeteoWeatherProvider` as `data_provider` for live weather; until data
    arrives the frontend shows `content` (or "Loading weather...").
    """

    type = "weather"
