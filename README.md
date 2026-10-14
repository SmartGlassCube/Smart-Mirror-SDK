# Smart-Mirror-SDK

A local-first Python SDK for gesture-controlled smart mirrors: webcam → hand gestures → pages and widgets → React UI over WebSocket.

## Dev quickstart (Mongo + dashboard)

```bash
git clone <this repo> && cd Smart-Mirror-SDK
./dev.sh up                  # first run: creates .env, downloads Mongo, seeds dev data
# open http://localhost:5174, log in with the admin user/password printed above
#   (after the first run: the password lives in .env -- DASHBOARD_ADMIN_PASSWORD)
./dev.sh down                # when you're done
```

No sudo, no manual Mongo/mongosh/user setup, ever -- `./dev.sh up` is idempotent,
safe to re-run from any state (fresh clone, already running, after a reboot
or a crash). It also starts a standalone content-sync daemon (Mongo -> Qdrant),
so editing content through the dashboard reaches the assistant's RAG and the
mirror's cached widget data **live** -- not just Mongo. First run installs the
`data`/`assistant` extras for that (torch included, can take a few minutes).

| Command | What it does |
|---|---|
| `./dev.sh up [--sync-admin-password]` | Start Mongo + content-sync daemon + dashboard backend (`:8000`) + frontend (`:5174`). Reuses whatever's already running. |
| `./dev.sh down` | Stop all four. |
| `./dev.sh status` | Up/down, PRIMARY?, last content sync, doc counts, dashboard user list. |
| `./dev.sh logs {mongo\|backend\|frontend\|content-sync}` | Tail that component's log. |
| `./dev.sh mongosh [args]` | Run the bundled mongosh against `MONGO_URI`. |
| `./dev.sh reset-password <user> [pw]` | Set/create a password; omit it to get one generated. |
| `./dev.sh reseed [--yes]` | **Destructive**: wipe + reseed dev content. |
| `./dev.sh mirror` | Run the full camera-driven `examples/mvp.py` with `MONGO_URI` from `.env`. Stops the content-sync daemon first (Qdrant's local storage can't be held by both at once) -- `up` restarts it afterward. |
| `./dev.sh install-autostart` / `uninstall-autostart` | A systemd `--user` unit to run Mongo at login (not enabled automatically). |

See [OVERNIGHT_REPORT.md](OVERNIGHT_REPORT.md) and [WORK_REPORT.md](WORK_REPORT.md)
for how this was built and verified.

## How to start developing (mirror only, no Mongo/dashboard)

From the repo root:

```bash
uv venv .venv
source .venv/bin/activate          # Windows (Git Bash): source .venv/Scripts/activate
uv pip install -e ".[data,dev]"
python examples/mvp.py             # needs a webcam and Node/npm for the UI
python -m pytest                   # unit tests, no camera needed
```

`uv run pytest` works out of the box (pytest is a default `uv sync` dependency
group, not an opt-in extra) but the assistant/content test suites need the
heavier `data`/`assistant` extras installed once: `uv sync --extra data --extra assistant`.
After that, plain `uv run pytest ...` keeps using them (`uv sync` on its own
re-trims back to just the defaults -- that's the one command to avoid).

- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md): architecture and module tour
- [docs/extending.md](docs/extending.md): add your own gestures, widgets and pages
- [docs/vision/README.md](docs/vision/README.md): the gesture pipeline and signals
