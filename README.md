# Smart-Mirror-SDK

A local-first Python SDK for gesture-controlled smart mirrors: webcam → hand gestures → pages and widgets → React UI over WebSocket.

## How to start developing

From the repo root:

```bash
uv venv .venv
source .venv/bin/activate          # Windows (Git Bash): source .venv/Scripts/activate
uv pip install -e ".[data,dev]"
python examples/mvp.py             # needs a webcam and Node/npm for the UI
python -m pytest                   # unit tests, no camera needed
```

- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md): architecture and module tour
- [docs/extending.md](docs/extending.md): add your own gestures, widgets and pages
- [docs/vision/README.md](docs/vision/README.md): the gesture pipeline and signals
