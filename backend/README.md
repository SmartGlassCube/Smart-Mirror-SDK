# Backend: the `smartmirror` package

Camera → gestures → page/widget state → WebSocket, plus the voice assistant and the
Mongo content sync. Module tour: [docs/architecture.md](../docs/architecture.md).

```bash
uv sync --extra data --extra assistant   # backend/.venv; plain `uv sync` = gestures + server only
uv run python -m smartmirror             # the mirror app (also starts ../frontend unless SMARTMIRROR_FRONTEND=0)
uv run pytest                            # tests, no camera needed
```

Without uv: `python -m venv .venv`, activate it, `pip install -e ".[data,assistant,dev]"`.

| Path | |
|---|---|
| `smartmirror/app/` | The mirror app: `settings.py` (env vars), `pages.py` (widgets + page graph), `main.py` |
| `smartmirror/server/` | `SmartMirrorServer`: WebSocket, camera loop, widget refresh, assistant hooks |
| `smartmirror/{vision,core,widgets,assistant,content,hal,config}/` | The SDK pieces, usable on their own |
| `tests/` | One folder per package |
| `scripts/` | `lan_media_server.py` (share a camera/mic over the LAN), `content_sync_daemon.py` (used by `../dev.sh`), `run_supervised.sh` (restart on crash), checks |
| `examples/` | `gesture_detector_debug.py`: annotated camera window + gesture feed |
| `.env.example` | Every setting. Copy to `.env` |
| `.data/` | Runtime files (hand model, Qdrant store, content cache), gitignored. Move with `SMARTMIRROR_DATA_DIR` |
