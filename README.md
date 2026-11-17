# Smart-Mirror-SDK

A local-first SDK for gesture-controlled smart mirrors: webcam → hand gestures → pages and widgets → React UI over WebSocket, plus a voice assistant.

| Folder | What | Stack |
|---|---|---|
| [`backend/`](backend/README.md) | The `smartmirror` Python package (vision, state, widgets, assistant, content sync, server) and the mirror app | Python, uv |
| [`frontend/`](frontend/README.md) | The mirror's UI | React, TypeScript, Vite |
| [`docs/`](docs/) | [Architecture](docs/architecture.md), [backend ↔ frontend protocol](docs/protocol.md), [extending](docs/extending.md), [vision](docs/vision.md), [voice testing](docs/voice-pipeline-testing.md) | |

The two halves share no code: they talk only over the WebSocket described in [docs/protocol.md](docs/protocol.md).

## Install from PyPI

```bash
pip install smartmirror        # or "smartmirror[assistant]" for the voice assistant
smartmirror                    # then open http://localhost:8080
```

The package ships a prebuilt copy of the UI, so it needs no Node. See [backend/README.md](backend/README.md)
(also the PyPI page) for building your own mirror. Releases: push a `vX.Y.Z` tag matching
`backend/smartmirror/__init__.py`; [publish.yml](.github/workflows/publish.yml) builds and uploads it.

## Quickstart from a checkout (mirror only, no Mongo)

Needs [uv](https://docs.astral.sh/uv/), Node/npm and a webcam.

```bash
cd backend
uv sync --extra data --extra assistant   # first time: creates backend/.venv (pulls in torch)
uv run python -m smartmirror             # backend on :8080, also starts the frontend on :5173
```

Tests: `cd backend && uv run pytest`. Settings: copy `backend/.env.example` to `backend/.env`.

## Club content (Dashboard + Mongo)

Content management (events, announcements, about, achievements, board) and MongoDB
itself are owned by the separate [`Dashboard`](https://github.com/SmartGlassCube/Dashboard) repo.
The two repos depend on each other only through MongoDB and
[`infra/mongo/CONTRACT.md`](https://github.com/SmartGlassCube/Dashboard/blob/main/infra/mongo/CONTRACT.md).
Start that repo's `./dev.sh up` first, then:

| Command | What it does |
|---|---|
| `./dev.sh up` | Start the content-sync daemon (Mongo → assistant RAG + cached widget data). Installs the backend extras on first run. |
| `./dev.sh down` | Stop it. |
| `./dev.sh status` | Mongo reachable? Content sync up / last sync? Mirror app up? |
| `./dev.sh logs` | Tail the content-sync daemon's log. |
| `./dev.sh mirror` | Run the full mirror app with `MONGO_URI` from `backend/.env`. Stops the content-sync daemon first: Qdrant's local storage can't be held by both. |

`./dev.sh up` is idempotent, safe to re-run from any state.

## Camera and mic on another machine

For a mirror (e.g. a Raspberry Pi) without its own camera or microphone, run
`uv run python scripts/lan_media_server.py --allow <mirror-ip>` in `backend/` on a machine
that has them, and point the mirror's `SMARTMIRROR_CAMERA` / `SMARTMIRROR_MIC` at it
(see `backend/.env.example`).

Past work logs: [docs/history/](docs/history/).
