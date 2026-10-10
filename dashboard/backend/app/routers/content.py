"""Generic CRUD router factory for the five content collections.

One instance per collection (events/announcements/about/achievements/board),
parametrized by its Pydantic In/Out models and which long-text fields get
the non-blocking English check. created_at/updated_at/updated_by are always
set here from the server clock + the logged-in user -- never trusted from
the client, even though they're present on the In models' sibling Out model.
"""

from datetime import datetime, timezone
from typing import Type

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo.database import Database
from pymongo.errors import WriteError

from ..audit import write_audit
from ..auth import CurrentUser, get_current_user
from ..db import get_db
from ..language import english_warnings


def _doc_out(doc: dict) -> dict:
    out = dict(doc)
    out["id"] = str(out.pop("_id"))
    return out


def _object_id(doc_id: str) -> ObjectId:
    try:
        return ObjectId(doc_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Not found")


def _validation_detail(error: WriteError) -> dict:
    return {"message": "Document failed validation", "mongo": getattr(error, "details", None) or {}}


def make_content_router(
    name: str,
    in_model: Type[BaseModel],
    out_model: Type[BaseModel],
    long_text_fields: tuple = (),
) -> APIRouter:
    router = APIRouter(prefix=f"/api/{name}", tags=[name])

    def _set_status(db: Database, user: CurrentUser, doc_id: str, status: str) -> dict:
        oid = _object_id(doc_id)
        now = datetime.now(timezone.utc)
        result = db[name].update_one(
            {"_id": oid}, {"$set": {"status": status, "updated_at": now, "updated_by": user.username}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Not found")
        write_audit(db, user.username, name, doc_id, f"status:{status}")
        return _doc_out(db[name].find_one({"_id": oid}))

    @router.get("", response_model=list[out_model])
    def list_items(
        status: str = None,
        db: Database = Depends(get_db),
        _user: CurrentUser = Depends(get_current_user),
    ):
        query = {"status": status} if status else {}
        docs = db[name].find(query).sort("updated_at", -1)
        return [_doc_out(d) for d in docs]

    @router.get("/{doc_id}", response_model=out_model)
    def get_item(doc_id: str, db: Database = Depends(get_db), _user: CurrentUser = Depends(get_current_user)):
        doc = db[name].find_one({"_id": _object_id(doc_id)})
        if doc is None:
            raise HTTPException(status_code=404, detail="Not found")
        return _doc_out(doc)

    @router.post("")
    def create_item(body: in_model, db: Database = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
        now = datetime.now(timezone.utc)
        doc = body.model_dump(exclude_none=True)
        doc["created_at"] = now
        doc["updated_at"] = now
        doc["updated_by"] = user.username
        try:
            result = db[name].insert_one(doc)
        except WriteError as error:
            raise HTTPException(status_code=422, detail=_validation_detail(error))
        write_audit(db, user.username, name, str(result.inserted_id), "create")
        warnings = english_warnings({field: doc.get(field) for field in long_text_fields})
        created = db[name].find_one({"_id": result.inserted_id})
        return {**_doc_out(created), "warnings": warnings}

    @router.put("/{doc_id}")
    def update_item(
        doc_id: str, body: in_model, db: Database = Depends(get_db), user: CurrentUser = Depends(get_current_user)
    ):
        oid = _object_id(doc_id)
        existing = db[name].find_one({"_id": oid})
        if existing is None:
            raise HTTPException(status_code=404, detail="Not found")
        doc = body.model_dump(exclude_none=True)
        doc["created_at"] = existing["created_at"]
        doc["updated_at"] = datetime.now(timezone.utc)
        doc["updated_by"] = user.username
        try:
            db[name].replace_one({"_id": oid}, doc)
        except WriteError as error:
            raise HTTPException(status_code=422, detail=_validation_detail(error))
        write_audit(db, user.username, name, doc_id, "update")
        warnings = english_warnings({field: doc.get(field) for field in long_text_fields})
        updated = db[name].find_one({"_id": oid})
        return {**_doc_out(updated), "warnings": warnings}

    @router.delete("/{doc_id}", status_code=204)
    def delete_item(doc_id: str, db: Database = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
        oid = _object_id(doc_id)
        result = db[name].delete_one({"_id": oid})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Not found")
        write_audit(db, user.username, name, doc_id, "delete")

    @router.patch("/{doc_id}/publish", response_model=out_model)
    def publish_item(doc_id: str, db: Database = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
        return _set_status(db, user, doc_id, "published")

    @router.patch("/{doc_id}/unpublish", response_model=out_model)
    def unpublish_item(doc_id: str, db: Database = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
        return _set_status(db, user, doc_id, "draft")

    return router
