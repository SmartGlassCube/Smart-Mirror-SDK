"""Verifies the local dev Mongo setup. Run with mongod already started:
    ./infra/mongo/dev_mongod.sh start
    uv run python infra/mongo/verify_phase_a.py

Checks: seed counts match seed.js, an invalid `events` doc is rejected by the
schema validator, a change stream observes a delete, and init_db.js is
idempotent (safe to re-run).
"""
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import WriteError

URI = "mongodb://localhost:27017/?directConnection=true"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> int:
    client = MongoClient(URI)
    db = client["ieee"]
    ok = True

    print("=== a) countDocuments per collection (vs seed.js) ===")
    expected = {"events": 4, "announcements": 2, "about": 2, "achievements": 1, "board": 2}
    for coll, exp in expected.items():
        got = db[coll].count_documents({})
        match = got == exp
        ok &= match
        print(f"  {coll}: expected={exp} got={got} {'OK' if match else 'MISMATCH'}")

    print("\n=== b) inserting an invalid doc into events is REJECTED ===")
    try:
        db.events.insert_one({"name": "x", "when": "next friday"})
        print("  FAIL: insert succeeded, should have been rejected")
        ok = False
    except WriteError as error:
        print(f"  OK: insert rejected -- {error}")

    print("\n=== c) change stream receives a 'delete' operationType ===")
    now = datetime.datetime.now(datetime.timezone.utc)
    tmp = db.events.insert_one({
        "status": "draft", "created_at": now, "updated_at": now, "updated_by": "verify-script",
        "title": "temp for delete test", "description": "temp", "start": now,
    })
    doc_id = tmp.inserted_id

    stream = db.events.watch(full_document="updateLookup")
    db.events.delete_one({"_id": doc_id})

    deadline = time.monotonic() + 10
    seen = None
    while time.monotonic() < deadline:
        change = stream.try_next()
        if change is None:
            time.sleep(0.1)
            continue
        if change["operationType"] == "delete" and change["documentKey"]["_id"] == doc_id:
            seen = change
            break
    stream.close()
    if seen:
        print(f"  OK: got delete event -- documentKey={seen['documentKey']}")
    else:
        print("  FAIL: no delete event observed within timeout")
        ok = False

    print("\n=== d) re-running init_db.js is idempotent ===")
    before_counts = {c: db[c].count_documents({}) for c in expected}
    result = subprocess.run(
        [str(REPO_ROOT / "infra/mongo/dev_mongod.sh"), "init"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    print("  stdout:", result.stdout.strip())
    after_counts = {c: db[c].count_documents({}) for c in expected}
    idempotent = result.returncode == 0 and before_counts == after_counts
    ok &= idempotent
    print(f"  {'OK' if idempotent else 'FAIL'}: exit code {result.returncode}, counts unchanged={before_counts == after_counts}")

    print("\n=== SUMMARY ===")
    print(json.dumps({"all_checks_passed": ok}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
