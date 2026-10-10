from datetime import datetime, timezone

from pymongo.database import Database


def write_audit(db: Database, username: str, collection: str, document_id: str, operation: str, changes: dict = None) -> None:
    db.audit_log.insert_one({
        "username": username,
        "collection": collection,
        "document_id": document_id,
        "operation": operation,
        "at": datetime.now(timezone.utc),
        "changes": changes,
    })
