import asyncio
import json
import urllib.request

USER_AGENT = "glasscube (https://github.com/SmartGlassCube/Smart-Mirror-SDK)"


def pick(value, path):
    """`path` ("quotes.0.text") walks into dicts by key and lists by index; "" returns `value`."""
    for part in filter(None, (path or "").split(".")):
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.lstrip("-").isdigit() and -len(value) <= int(part) < len(value):
            value = value[int(part)]
        else:
            return None
    return value


class HttpJsonProvider:
    """GETs a JSON URL and returns it, or the part of it at `path` ("a.b.0").

    Same behaviour as Smart Mirror Studio's "JSON API" data source.
    """

    def __init__(self, url, path="", timeout=10, headers=None):
        self.url = url
        self.path = path
        self.timeout = timeout
        self.headers = {"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})}

    def fetch(self):
        request = urllib.request.Request(self.url, headers=self.headers)
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return pick(json.load(response), self.path)

    async def __call__(self, _widget=None):
        # In a worker thread: a blocking HTTP call here would freeze the camera loop.
        return await asyncio.to_thread(self.fetch)
