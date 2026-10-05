import asyncio
import io
import json
import urllib.parse

from smartmirror.widgets.providers import OpenMeteoWeatherProvider
from smartmirror.widgets.providers import open_meteo


def test_open_meteo_maps_current_weather(monkeypatch):
    requested = []
    payload = {
        "current": {
            "temperature_2m": 26.2,
            "relative_humidity_2m": 56,
            "wind_speed_10m": 13.4,
            "weather_code": 1,
            "is_day": 1,
        }
    }

    def fake_urlopen(url, timeout):
        requested.append(url)
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(open_meteo.urllib.request, "urlopen", fake_urlopen)
    provider = OpenMeteoWeatherProvider(latitude=36.8065, longitude=10.1815, city="Tunis")

    assert asyncio.run(provider()) == {
        "city": "Tunis",
        "temperature": 26.2,
        "humidity": 56,
        "wind": 13.4,
        "code": 1,
        "isDay": True,
    }
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(requested[0]).query)
    assert query["latitude"] == ["36.8065"] and query["longitude"] == ["10.1815"]
