from datetime import datetime
import importlib
import dotenv

dotenv.load_dotenv()

class QRCodeCatalogProvider:
    def __init__(self, categories):
        self.categories = categories or {}

    def __call__(self, _widget=None):
        return {"categories": self.categories}


class MongoCalendarProvider:
    def __init__(self, uri, database, collection, query=None, projection=None, limit=20, sort_field="start"):
        self.uri = uri
        self.database = database
        self.collection_name = collection
        self.query = query or {}
        self.projection = projection or {
            "_id": 0,
            "title": 1,
            "start": 1,
            "end": 1,
            "location": 1,
            "description": 1,
        }
        self.limit = limit
        self.sort_field = sort_field

    def _to_json_safe(self, value):
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, list):
            return [self._to_json_safe(item) for item in value]
        if isinstance(value, dict):
            return {key: self._to_json_safe(item) for key, item in value.items()}
        return value

    def __call__(self, _widget=None):
        try:
            pymongo = importlib.import_module("pymongo")
            MongoClient = getattr(pymongo, "MongoClient")
        except ImportError as error:
            raise RuntimeError("pymongo is required for MongoCalendarProvider") from error

        with MongoClient(self.uri) as client:
            collection = client[self.database][self.collection_name]
            cursor = (
                collection.find(self.query, self.projection)
                .sort(self.sort_field, 1)
                .limit(self.limit)
            )
            events = [self._to_json_safe(document) for document in cursor]

        return {"events": events}
