from datetime import datetime


class MongoCalendarProvider:
    """Reads calendar events from MongoDB. Returns `{"events": [...]}` with datetimes as ISO strings.

    Requires the `data` extra (`pip install glasscube[data]`).
    """

    DEFAULT_PROJECTION = {"_id": 0, "title": 1, "start": 1, "end": 1, "location": 1, "description": 1}

    def __init__(self, uri, database, collection, query=None, projection=None, limit=20, sort_field="start"):
        self.uri = uri
        self.database = database
        self.collection_name = collection
        self.query = query or {}
        self.projection = projection or self.DEFAULT_PROJECTION
        self.limit = limit
        self.sort_field = sort_field

    def __call__(self, _widget=None):
        try:
            from pymongo import MongoClient
        except ImportError as error:
            raise RuntimeError("pymongo is required for MongoCalendarProvider (pip install glasscube[data])") from error

        with MongoClient(self.uri) as client:
            cursor = (
                client[self.database][self.collection_name]
                .find(self.query, self.projection)
                .sort(self.sort_field, 1)
                .limit(self.limit)
            )
            return {"events": [_to_json_safe(document) for document in cursor]}


def _to_json_safe(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_json_safe(item) for key, item in value.items()}
    return value
