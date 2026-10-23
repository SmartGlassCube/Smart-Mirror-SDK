# Smart-Mirror-SDK

A local-first Python SDK for gesture-controlled smart mirrors: webcam → hand gestures → pages and widgets → React UI over WebSocket.

## The dashboard lives in a separate repo

Content management (events, announcements, about, achievements, board) and
MongoDB itself are owned by [`Dashboard`](https://github.com/SmartGlassCube/Dashboard) --
a separate repo, on purpose: the two depend on each other only through
MongoDB + [`infra/mongo/CONTRACT.md`](https://github.com/SmartGlassCube/Dashboard/blob/main/infra/mongo/CONTRACT.md)
in that repo, no shared code. Start that repo's `./dev.sh up` first, then
come back here.

## Dev quickstart (content sync + mirror)

```bash
git clone <this repo> && cd Smart-Mirror-SDK
# ../Dashboard/dev.sh up must already be running -- see above
./dev.sh up                  # starts the content-sync daemon (Mongo -> RAG + widget cache)
./dev.sh mirror               # the full camera-driven mirror app (stops the daemon first, see below)
./dev.sh down                 # stop the content-sync daemon
```

No manual Mongo/mongosh setup here -- `./dev.sh up` is idempotent, safe to
re-run from any state. First run installs the `data`/`assistant` extras
(torch included, can take a few minutes) the content-sync daemon needs.

| Command | What it does |
|---|---|
| `./dev.sh up` | Start the content-sync daemon (Mongo -> assistant RAG + mirror's cached widget data). Needs Mongo reachable -- see `./dev.sh status`. |
| `./dev.sh down` | Stop it. |
| `./dev.sh status` | Mongo reachable? + content-sync up/last-sync + mirror app up? |
| `./dev.sh logs` | Tail the content-sync daemon's log. |
| `./dev.sh mirror` | Run the full camera-driven `examples/mvp.py` with `MONGO_URI` from `.env`. Stops the content-sync daemon first (Qdrant's local storage can't be held by both at once) -- `up` restarts it afterward. |

See [OVERNIGHT_REPORT.md](OVERNIGHT_REPORT.md) and [WORK_REPORT.md](WORK_REPORT.md)
for how this (and the split from the Dashboard repo) was built and verified.

## How to start developing (mirror only, no Mongo/dashboard)

From the repo root:

```bash
uv venv .venv
source .venv/bin/activate          # Windows (Git Bash): source .venv/Scripts/activate
uv pip install -e ".[assistant,data,dev]"
python examples/mvp.py             # needs a webcam and Node/npm for the UI
python -m pytest                   # unit tests, no camera needed
```

`uv run pytest` works out of the box (pytest is a default `uv sync` dependency
group, not an opt-in extra) but the assistant/content test suites need the
heavier `data`/`assistant` extras installed once: `uv sync --extra data --extra assistant`.
After that, plain `uv run pytest ...` keeps using them (`uv sync` on its own
re-trims back to just the defaults -- that's the one command to avoid).

`smartmirror/content/tests` need a **running Mongo** -- they read `MONGO_URI`
from the environment and skip with a clear message (pointing at
`../Dashboard/dev.sh up`) if it's not reachable, rather than failing.

- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md): architecture and module tour
- [docs/extending.md](docs/extending.md): add your own gestures, widgets and pages
- [docs/vision/README.md](docs/vision/README.md): the gesture pipeline and signals
