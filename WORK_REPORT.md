# Work report -- `./dev.sh` and the uv footgun fix

Ran on `amin/content-sync` (2026-10-14 -> 2026-10-15), on top of the
overnight session (`OVERNIGHT_REPORT.md`). Three commits, nothing pushed or
merged.

## Addendum (2026-10-15): the dashboard wasn't actually reaching the RAG

Asked directly: "does updating the db actually update the RAG, not just
widgets?" -- it's a fair thing to not take on faith. Checked, and the honest
answer at the time was **no, not continuously**: the dashboard writes
straight to Mongo, but nothing was running the mirror's Mongo->Qdrant sync
in the dev stack `./dev.sh up` brought up (that sync only runs inside
`examples/mvp.py`, which `up` never started). Proved the gap concretely
(created an event via the dashboard API, queried the assistant's retriever,
got nothing back), then closed it: `scripts/content_sync_daemon.py` runs
the same `ContentSync.reconcile()` + `.watch()` + heartbeat the mirror runs
on boot, with no camera/gestures/UI attached, and `./dev.sh up` now starts
it. Re-verified live end to end afterward -- see "Content-sync daemon
verification" below. Commit: `dba4db1`.

One real constraint surfaced along the way: Qdrant's embedded (local-mode)
storage takes an **exclusive lock** on its directory (confirmed by trying
to open the same path twice -- the second open raises). The standalone
daemon and `examples/mvp.py`'s own internal sync can't both hold that lock
at once, so `./dev.sh mirror` now stops the daemon first and `up` brings it
back afterward, instead of the mirror app crashing on a lock error.

### Content-sync daemon verification (exact steps, no manual reconcile)

1. Logged into the dashboard API, `POST /api/announcements` with a new
   published announcement ("Hackathon Registration Open").
2. Within ~2s, `smartmirror/content/.cache/cache.json` contained it --
   proof the **change-stream watcher** picked it up live, not a
   reconcile-on-boot I triggered myself.
3. Paused the daemon just long enough to safely open its Qdrant store from
   a one-off script (can't open it while the daemon holds the lock) and
   ran `Retriever.retrieve("Is hackathon registration open?")` -- the new
   announcement came back as the top match.
4. Deleted it via the API; the cache entry disappeared within ~2s, no
   manual steps.
5. Restarted the daemon with `./dev.sh up` (idempotent, as designed) and
   re-ran `smartmirror/content/tests` (33 passed) to confirm nothing in the
   shared `smartmirror.content` package regressed.

## Status: done

- `./dev.sh` at repo root: `up`, `down`, `status`, `logs`, `mongosh`,
  `reset-password`, `reseed`, `mirror`, `install-autostart`,
  `uninstall-autostart`, `help`. See the README's "Dev quickstart" table.
- Root `.env` (gitignored, `.env.example` committed) is the single source
  of truth for `MONGO_URI` / `DASHBOARD_ADMIN_USER` / `DASHBOARD_ADMIN_PASSWORD`
  / `DASHBOARD_JWT_SECRET`, shared by the mirror, the dashboard backend, and
  `dev.sh`. `dashboard/backend/app/config.py` now loads it via
  `python-dotenv` (root wins over `dashboard/backend/.env` if both exist).
- `infra/mongo/dev_mongod.sh`: auto-downloads mongod/mongosh if `.bin/` is
  missing, cleans up a stale pidfile, fails loudly (not silently) if mongod
  never comes up, and refuses with a clear message if port 27017 is held by
  something that isn't its own mongod. New `seed-if-empty` subcommand.
- Admin bootstrap (`dashboard/backend/scripts/bootstrap_admin.py`): creates
  the `.env`-configured admin if missing, leaves an existing password alone
  unless `--sync-admin-password`, and cleans up the overnight session's
  `admin`/`supersecret123` throwaway credential -- **including the edge case
  where it's the same username as the configured admin** (checked by
  verifying the password hash against the known throwaway password, not
  just comparing usernames -- see "found during testing" below).
- uv footgun: added `[dependency-groups] dev` to the root `pyproject.toml`.
  `uv run which pytest` now resolves to `.venv/bin/pytest` on a bare
  `uv sync`, no `--extra` flags needed.

## Found and fixed during testing (not in the original ask, but real)

**The default admin bootstrap did nothing on the very first real run.**
`.env.example` defaults `DASHBOARD_ADMIN_USER=admin` -- the same username the
overnight session's throwaway `admin`/`supersecret123` credential used. My
first version of `bootstrap_admin.py` only cleaned up the throwaway user
when its username *differed* from the configured one; here they matched, so
the cleanup branch was skipped entirely and the existing (throwaway) user
was left "untouched" by the normal keep-existing-password rule -- the freshly
generated password landed in `.env` but was never actually applied to the
account. Fixed by checking the *password hash* against the known throwaway
password regardless of username, and replacing it unconditionally in that
specific case (there's no real secret to protect there). Verified below.

## Verification (exact output)

### Cold start: `down` then `up`, login works

```
$ ./dev.sh down
dev.sh: frontend: not running
dev.sh: backend: not running
mongo: stopped

$ ./dev.sh up
dev.sh: .env missing -- creating it from .env.example with generated secrets
mongo: started (pid 173187)
ok: events / ok: announcements / ok: about / ok: achievements / ok: board
ok: mirror_status / ok: dashboard_users / ok: audit_log
mongo: content collections already have 11 doc(s) total, not reseeding
user 'admin' already exists, left untouched (pass --sync-password to overwrite)   <- the bug above
dev.sh: backend: up (pid 173377) -- http://localhost:8000
dev.sh: frontend: up (pid 173398) -- http://localhost:5174
================================================================
 Smart Mirror dev stack is up
================================================================
 ...
 Password:  XgjP3z8faONI6NiXywnd   (generated just now -- shown once; also saved in .env)
================================================================
```

After the `bootstrap_admin.py` fix and re-running `up`:
```
replaced known throwaway password for 'admin'
dev.sh: backend: already running (pid 173377)
dev.sh: frontend: already running (pid 173398)
```

Login with the `.env` credentials:
```
$ source .env
$ curl -s -i -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$DASHBOARD_ADMIN_USER\",\"password\":\"$DASHBOARD_ADMIN_PASSWORD\"}"
HTTP/1.1 200 OK
set-cookie: smartmirror_dashboard_session=eyJhbGciOiJIUzI1NiIs...; HttpOnly; Max-Age=28800; Path=/; SameSite=lax
{"username":"admin","role":"admin"}
```

### `up` twice -- no duplicates, no data loss

Doc counts before and after the second `up` (events/announcements/about/achievements/board):
```
before: 4 2 2 1 2
after:  4 2 2 1 2
```
Second run's log: `mongo: already running`, `backend: already running`,
`frontend: already running` -- nothing restarted, no duplicate processes.

### `kill -9` on mongod, then `up` -> recovers

```
$ kill -9 173187
$ ./dev.sh up
... mongo: started (pid 173617) ...
ok: events / ... / ok: audit_log
mongo: content collections already have 11 doc(s) total, not reseeding
```
Doc counts after recovery: unchanged (4/2/2/1/2). Login still returns 200.

### `reset-password amin` -> login works with the new password

```
$ ./dev.sh reset-password amin
created admin user 'amin'
generated password for 'amin': lyvSluMPZbrx570aFb42
(shown once -- store it now)

$ curl -s -i -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" -d '{"username":"amin","password":"lyvSluMPZbrx570aFb42"}'
HTTP/1.1 200 OK
{"username":"amin","role":"admin"}
```

### `./dev.sh mongosh --quiet --eval 'db.events.countDocuments()'`

```
$ ./dev.sh mongosh --quiet --eval 'db.events.countDocuments()'
4
```

### Port conflict -> clear error, not a hang

Occupied port 8000 with a dummy listener, then ran `up`:
```
dev.sh: ERROR: port 8000 is already in use by something else (not managed by dev.sh) -- free it or edit BACKEND_PORT in dev.sh
```
Real exit code: `1`. Frontend was correctly never started (the script aborts
on the backend failure, per `set -euo pipefail`) -- confirmed `curl` to
`:5174` got connection-refused (`000`) right after.

### `install-autostart` / `uninstall-autostart`

```
$ ./dev.sh install-autostart
dev.sh: installed /home/hefouzinho/.config/systemd/user/smartmirror-mongo.service
Not enabled or started (your call). To do that yourself:
  systemctl --user enable --now smartmirror-mongo.service
...
$ systemctl --user is-enabled smartmirror-mongo.service
disabled
$ ./dev.sh uninstall-autostart
dev.sh: removed .../smartmirror-mongo.service
```
Confirmed `disabled` -- `install-autostart` only writes the unit file and
`daemon-reload`s, never enables or starts it.

### uv footgun fix

```
$ uv sync                      # bare, no --extra flags
 - torch==2.14.1 / - mediapipe==1.1.0 / - pymongo==4.18.3 / ...   (trimmed to defaults)
$ uv run which pytest
/home/hefouzinho/Smart-Mirror-SDK/.venv/bin/pytest
```
Confirms `uv run` always finds `.venv`'s own pytest now, regardless of
whether the heavier extras are currently installed. Restored them with
`uv sync --extra dev --extra assistant --extra data` for the test run below,
then confirmed a **bare** `uv run pytest --version` afterward does *not*
strip them back out (only explicit `uv sync` with no `--extra` does that) --
so this is a one-time-per-fresh-env step, not something that needs
repeating before every test run.

### All test suites

```
$ CUDA_VISIBLE_DEVICES="" uv run pytest tests/ smartmirror/assistant/tests/ smartmirror/content/tests -q
156 passed in 82.43s

$ cd dashboard/backend && uv run pytest tests -q
18 passed in 10.08s

$ cd dashboard/frontend && npm run build
✓ built in 694ms   (0 TypeScript errors)
```

## Current state (left running)

```
$ ./dev.sh status
Mongo:
  up (PRIMARY)
Backend (:8000):
  up
Frontend (:5174):
  up
Content doc counts:
  events: 4, announcements: 2, about: 2, achievements: 1, board: 2, mirror_status: 1
Dashboard users:
  admin (admin)
  amin (admin)
```

Left the stack running since "one command brings it up" is the whole point --
`./dev.sh down` whenever you want it stopped. Two admin users now exist:
`admin` (password in `.env`, the overnight throwaway credential's password is
gone -- see "found during testing" above) and `amin` (created by the
`reset-password` verification step above, password
`lyvSluMPZbrx570aFb42` -- rotate or delete it if you don't want it).

## NEEDS YOU

Nothing requiring sudo or elevated rights this time -- everything in this
task was achievable with project-local installs and no system changes.
Carried over from `OVERNIGHT_REPORT.md` (still applies, not re-verified here):

1. `sudo usermod -aG docker $USER` + relogin, if you want real `docker
   compose` instead of the tarball fallback.
2. `sudo ufw allow from 192.168.0.0/16 to any port 27017` (and change
   `dev_mongod.sh`'s `--bind_ip` to `0.0.0.0`) -- only once the Pi needs to
   reach this PC's Mongo over LAN.
3. If you want Mongo running at login without manually running `./dev.sh up`
   every time: `./dev.sh install-autostart` (I did not enable it --
   `systemctl --user enable --now smartmirror-mongo.service` is yours to
   run), optionally followed by `loginctl enable-linger $USER` if you want
   it to survive logging out entirely (that one may need sudo depending on
   your system's polkit rules).
4. Rotate/delete the `amin` user created during `reset-password` testing
   (password above) if you don't want it around.

## Decisions worth a second look

- **`DASHBOARD_ADMIN_USER` defaults to `admin` in `.env.example`.** This is
  exactly the overnight throwaway credential's username, which is *why* the
  bug above surfaced immediately on the very first real test. Bootstrap
  logic now handles it correctly either way, but if you'd rather the
  default not collide with that name at all, change it in `.env.example`
  (and your own `.env`, if you've already generated one).
- **`up`'s per-service health checks are process-liveness, not deep
  health.** "Already running" means "a process matching the expected
  binary+port is alive and (for backend/frontend) the HTTP health check
  passed at least once on startup" -- it doesn't re-probe health on every
  `up` for an already-running service. Fine for a dev tool; wouldn't be
  enough for anything that needs to self-heal a wedged-but-alive process.
  (Mongo is the exception: `status` always re-checks PRIMARY via a live
  `rs.status()` call, not just "is the process alive".)
- **PID files are informational/fast-path, `pgrep -f` pattern matching on
  the exact binary+port is the actual source of truth** for "is this
  running" and "what do I kill" -- this is deliberate: backgrounding
  `npm run dev &` earlier this week left a stray `vite` process alive for
  four days because killing the `npm` wrapper's PID didn't kill its child.
  `dev.sh` invokes `.venv/bin/uvicorn` and `node_modules/.bin/vite` directly
  (no `uv run`/`npm run` wrapper in between) specifically to avoid that
  class of bug, and `pgrep -f` as the fallback/self-healing path means a
  stale or missing pidfile can't cause a duplicate start or an unkillable
  orphan either.
- **No per-port configurability exposed on the CLI** -- `BACKEND_PORT`/
  `FRONTEND_PORT` are constants at the top of `dev.sh`, not flags or env
  vars. Simple for now; shout if you ever need two stacks running side by
  side.
- **`./dev.sh up` now installs the `data`+`assistant` extras (torch
  included) on first run**, for the content-sync daemon's embedder. That's
  a meaningfully heavier default footprint than before (`up` used to only
  need the lightweight dashboard backend venv + frontend node_modules).
  Accepted deliberately -- you asked for dashboard edits to reach the RAG
  live, and that requires an embedding model running somewhere. The daemon
  uses the GPU by default (same as the rest of the assistant stack); this
  machine's GPU is small enough that heavy concurrent use elsewhere
  (Ollama, the full mirror app) could still contend for it -- not observed
  as an actual problem during this session's testing, just flagging the
  same class of thing noted in `OVERNIGHT_REPORT.md`.
- **The content-sync daemon and `examples/mvp.py` can't run at the same
  time** (Qdrant's embedded storage lock, see above) -- `./dev.sh mirror`
  handles this for you, but if you ever start the mirror app some other
  way (not through `dev.sh`), stop the daemon first (`./dev.sh down`, or
  just kill the pid in `.dev/pids/content-sync.pid`) or it'll fail to open
  its Qdrant store.

## Commits

```
400e21b Add ./dev.sh: one idempotent command for the whole dev stack
cc83277 Add WORK_REPORT.md
dba4db1 dev.sh up: start a standalone content-sync daemon too
```

On top of the overnight session's 5 commits (`68c48a1`..`f821aa8`, see
`OVERNIGHT_REPORT.md`). Nothing pushed, nothing merged.
