#!/usr/bin/env python
"""Standalone Mongo -> cache + Qdrant content sync, no camera/gestures/UI.

Runs exactly what the mirror does for content on boot (ContentSync.reconcile()
then .watch() + heartbeat, see smartmirror.content.sync), so that editing
content through the dashboard reaches the assistant's RAG and the cached
widget data live -- without needing the full camera-driven mirror app
(python -m smartmirror) running. Started/stopped by ./dev.sh up|down.

Started by ./dev.sh with SMARTMIRROR_MIRROR_ID=dev-content-sync (default
"mirror-1" otherwise) so its mirror_status heartbeat doesn't look like a
real mirror in the dashboard's status page.

Requires MONGO_URI (see backend/.env). Logs to stdout. SIGTERM/SIGINT
trigger a clean shutdown (reconcile/watch/heartbeat all check a stop event
in <=0.5s steps, see ContentSync).

NOTE: Qdrant's embedded (local-mode) storage takes an exclusive lock on its
directory -- this daemon and the mirror app can't both have it open at
once. `./dev.sh mirror` stops this daemon first for exactly that reason.
"""
import asyncio
import logging
import os
import signal
import threading

from smartmirror.content import build_content_sync, enabled

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("content_sync_daemon")

os.environ.setdefault("SMARTMIRROR_MIRROR_ID", "dev-content-sync")


async def main() -> None:
    if not enabled():
        raise SystemExit("MONGO_URI is not set -- nothing to sync (see backend/.env).")

    content_sync = build_content_sync()
    logger.info(
        "starting (mirror_id=%s, mongo=%s, qdrant_collection=%s)",
        content_sync.config.mirror_id, content_sync.config.mongo_uri_redacted, content_sync.config.qdrant_collection,
    )

    stop_event = threading.Event()
    loop = asyncio.get_running_loop()

    def _request_stop(sig):
        if not stop_event.is_set():
            logger.info("got %s, shutting down...", sig.name)
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _request_stop, sig)

    await content_sync.run_forever(stop_event=stop_event)
    logger.info("stopped")


if __name__ == "__main__":
    asyncio.run(main())
