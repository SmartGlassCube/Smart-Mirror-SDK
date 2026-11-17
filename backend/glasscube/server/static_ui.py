"""The prebuilt mirror UI that ships inside the package, served over HTTP on the WebSocket port.

`frontend/` is built into `glasscube/ui/` when the package is built (see
scripts/build_frontend.py), so a pip install has a UI without Node: open
http://localhost:8080. In a checkout without that build, there's nothing to serve
and the app runs the Vite dev server instead (app/frontend_dev.py).
"""

import mimetypes
from http import HTTPStatus
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

from websockets.datastructures import Headers
from websockets.http11 import Response

UI_DIR = Path(__file__).resolve().parents[1] / "ui"

# Windows' registry can map .js to text/plain, which browsers refuse for module scripts.
_TYPES = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}


def bundled_ui_dir() -> Optional[Path]:
    """glasscube/ui/ when it holds a built UI, else None."""
    return UI_DIR if (UI_DIR / "index.html").is_file() else None


def is_websocket_upgrade(request) -> bool:
    return "websocket" in request.headers.get("Upgrade", "").lower()


def serve_ui_file(connection, request, root: Path):
    """GET <path> from `root` (`/` is index.html): a Response, or a 404 for a missing file."""
    path = unquote(request.path.split("?", 1)[0])
    relative = path.lstrip("/") or "index.html"
    file = (root / relative).resolve()
    if root.resolve() not in file.parents or not file.is_file():
        return connection.respond(HTTPStatus.NOT_FOUND, "Not found\n")
    body = file.read_bytes()
    headers = Headers({
        "Content-Type": _TYPES.get(file.suffix) or mimetypes.guess_type(file.name)[0] or "application/octet-stream",
        "Content-Length": str(len(body)),
        # Vite puts content hashes in everything under assets/; index.html must stay fresh.
        "Cache-Control": "max-age=31536000, immutable" if relative.startswith("assets/") else "no-cache",
    })
    return Response(HTTPStatus.OK, "OK", headers, body)
