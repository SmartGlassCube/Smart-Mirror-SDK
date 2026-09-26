import asyncio
import json
import urllib.parse
import urllib.request

API_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT_FIELDS = "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code,is_day"


class OpenMeteoWeatherProvider:
    """Current weather from Open-Meteo (free, no API key needed) for the `WeatherWidget`.

    Returns `{"city", "temperature", "humidity", "wind", "code", "isDay"}` in °C, % and km/h;
    `code` is the WMO weather code, which the frontend turns into a label and an icon.
    """

    def __init__(self, latitude, longitude, city="", timeout=10):
        self.latitude = latitude
        self.longitude = longitude
        self.city = city
        self.timeout = timeout

    def fetch(self):
        query = urllib.parse.urlencode(
            {"latitude": self.latitude, "longitude": self.longitude, "current": CURRENT_FIELDS, "timezone": "auto"}
        )
        with urllib.request.urlopen(f"{API_URL}?{query}", timeout=self.timeout) as response:
            current = json.load(response)["current"]
        return {
            "city": self.city,
            "temperature": current["temperature_2m"],
            "humidity": current["relative_humidity_2m"],
            "wind": current["wind_speed_10m"],
            "code": current["weather_code"],
            "isDay": bool(current["is_day"]),
        }

    async def __call__(self, _widget=None):
        # In a worker thread: a blocking HTTP call here would freeze the camera loop.
        return await asyncio.to_thread(self.fetch)
