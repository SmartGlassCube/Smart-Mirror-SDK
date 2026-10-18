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

---

# Repo split: dashboard/ + infra/mongo/ -> the Dashboard repo

Ran on 2026-10-18, unattended. Two repos now: **Smart-Mirror-SDK** (branch
`amin/content-sync`, 1 new commit) and **Dashboard**
(https://github.com/SmartGlassCube/Dashboard, branch `amin/fastapi-dashboard`,
2 new commits). Nothing pushed, nothing merged into either `main`.

## STEP 0 -- the existing Dashboard repo

Cloned `git@github.com:SmartGlassCube/Dashboard.git` into `../Dashboard`.
It's a **placeholder, not an implementation**: one commit ("Initial commit",
Moetez Fradi, 2025-12-18), containing only `LICENSE` (MIT, Smart Glass Cube)
and a 2-line `README.md` ("The dashboard that will be used by IEEE INSAT
bureau to add new data and events."). No stack chosen, no code, one branch
(`main`). Nothing to compare side-by-side against, nothing to overwrite, no
conflicting approach to reconcile -- all our work landed on a fresh branch
(`amin/fastapi-dashboard`) off `main`, with `main` itself untouched.

## STEP 1 -- building the Dashboard repo (branch `amin/fastapi-dashboard`)

**History preserved, as asked**: `git subtree split --prefix=dashboard -b dashboard-export`
in Smart-Mirror-SDK produced a 3-commit branch (`backend/`+`frontend/` at
its root, prefix stripped). Pulled into `../Dashboard` via a temporary local
remote and `git merge --allow-unrelated-histories` on top of `main` --
`git log --oneline --graph` on that branch shows the 3 original commits
(`e8de798`, `c9739b8`, `e39a9fc`) as real ancestors, not squashed:

```
*   43ea886 Merge dashboard-export from Smart-Mirror-SDK (backend/, frontend/, full history)
|\
| * e39a9fc Add ./dev.sh: one idempotent command for the whole dev stack
| * c9739b8 Phase C (frontend): dashboard/frontend -- React + TypeScript + Vite exec-board UI
| * e8de798 Phase C (backend): dashboard/backend -- FastAPI CRUD + auth + mirror monitoring
* 06b27ae Initial commit
```

**Layout: `backend/`, `frontend/` at the repo root** (not kept under a
`dashboard/` wrapper) -- the existing repo had no layout to defer to (see
STEP 0), and a dedicated repo whose whole purpose is the dashboard doesn't
need the extra nesting.

**`infra/mongo/` moved here, this repo now owns the database and the
contract.** Copied `CONTRACT.md`, `init_db.js`, `seed.js`,
`docker-compose.yml`, `dev_mongod.sh`, `verify_phase_a.py` as new files
(not subtree-split -- wasn't asked to preserve their history, and they're
small/mostly-static). Also physically copied the gitignored `.bin/`
(589M, the mongod/mongosh binaries) and `.data/` (411M, the live dev
dataset) on disk, so the running Mongo's actual data carried over instead
of starting from an empty seed -- confirmed by starting mongod from the new
location and getting the same doc counts as before the copy.

**Contract bumped to v0.4**: added a `_meta` collection (one doc,
`_id: "contract"`, written by `init_db.js`) that Smart-Mirror-SDK's content
sync reads to check compatibility. Hit a real gotcha here: `ieee._meta`
doesn't work via dot-access in **either** mongosh or pymongo -- both
special-case a leading underscore as colliding with their own internal
attributes (pymongo even raises a named error about it: `Database has no
attribute '_meta'. ... use database['_meta']`). Verified this directly
before working around it, rather than guessing. Fixed with
`getCollection("_meta")` in `init_db.js` and `db["_meta"]` in Python, kept
the literal `_meta` name as asked rather than renaming around the problem.

**`backend/app/config.py` path bug caught before it mattered**: the root-
`.env` loader was computed as `_BACKEND_DIR.parent.parent`, correct for the
*old* nested `dashboard/backend/app/config.py` (two levels up to repo
root) but one level too many for the new flat `backend/app/config.py` --
would have silently loaded nothing and fallen back to a random JWT secret
every restart. Fixed to `_BACKEND_DIR.parent`.

**`dev.sh`** (adapted from Smart-Mirror-SDK's, same robustness
guarantees): `up`/`down`/`status`/`logs`/`mongosh`/`reset-password`/
`reseed`/`install-autostart`/`uninstall-autostart` for Mongo + backend +
frontend + admin bootstrap. Own `.env`/`.env.example`.

**README**: dev quickstart, stack overview, and the relationship to
Smart-Mirror-SDK (Mongo-only, no shared code).

Committed as `8ea5114`.

### STEP 1 verification (exact output)

Cold `down` then `up`, from `../Dashboard`:
```
$ ./dev.sh down
dev.sh: frontend: stopped
dev.sh: backend: stopped
mongo: stopped
$ ./dev.sh up
mongo: content collections already have 11 doc(s) total, not reseeding
user 'admin' already exists, left untouched (pass --sync-password to overwrite)
dev.sh: backend: up (pid ...) -- http://localhost:8000
dev.sh: frontend: up (pid ...) -- http://localhost:5174
================================================================
 Dashboard dev stack is up
================================================================
 ...
================================================================
```

Login with the `.env` credentials:
```
$ source .env
$ curl -s -i -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$DASHBOARD_ADMIN_USER\",\"password\":\"$DASHBOARD_ADMIN_PASSWORD\"}"
HTTP/1.1 200 OK
set-cookie: smartmirror_dashboard_session=...; HttpOnly; Max-Age=28800; Path=/; SameSite=lax
{"username":"admin","role":"admin"}
```
(One real gotcha here too: the *migrated* `admin` user already existed with
its old password from the overnight session, so the newly-generated `.env`
password didn't actually work until I ran `./dev.sh up --sync-admin-password`
once -- expected behavior given the "don't overwrite an existing password"
rule, just a one-time migration step worth calling out.)

Backend tests and frontend build, from `../Dashboard` only:
```
$ cd backend && uv run pytest tests -q
18 passed, 1 warning in 10.08s
$ cd frontend && npm run build
✓ built in 801ms   (0 TypeScript errors)
```

## STEP 2 -- shrinking Smart-Mirror-SDK (branch `amin/content-sync`)

Removed `dashboard/` and `infra/mongo/` (`git rm -r --cached` + `rm -rf` --
confirmed gone from disk, not just untracked). Kept `smartmirror/content/`
and `scripts/content_sync_daemon.py`.

**Contract-version compatibility check**, as asked:
- `CONTRACT_VERSION = "0.4"` in `smartmirror/content/config.py`, matching
  the Dashboard repo's `init_db.js`.
- `ContentSync.check_contract_version()` reads the `_meta` doc on every
  `reconcile()` call and at `run_forever()` startup. A **major** version
  difference (the part before the first `.`) refuses to sync -- logs at
  `ERROR`, sets `last_error`, leaves the cache/Qdrant untouched, and (at
  the `run_forever` level) skips `watch()` entirely for that run, not just
  one `reconcile()` call. A **minor** difference is treated as compatible.
  Mongo being simply *unreachable* during the check is explicitly **not**
  treated as a mismatch -- it falls through to `reconcile()`/`watch()`'s
  own existing retry/backoff logic, so a Mongo that's briefly down at boot
  still recovers once it comes back (no regression from before this
  change). 3 new tests in `smartmirror/content/tests/test_sync.py`.

**`dev.sh` shrunk** to what's actually left here: `up`/`down` for the
content-sync daemon, `status` (Mongo reachable? + daemon + mirror app),
`logs`, `mirror`. Every command that needs Mongo and can't reach it now
fails with "start it from the Dashboard repo: ../Dashboard/dev.sh up"
instead of a raw connection error.

**Tests**: `smartmirror/content/tests/conftest.py`'s `MONGO_URI` is now
read from the environment (was hardcoded to `localhost`) with a skip
message pointing at `../Dashboard/dev.sh up` when unreachable.

**README + code comments**: updated to point at the Dashboard repo
wherever `infra/mongo/CONTRACT.md` or `dashboard/` used to be referenced
locally (`examples/mvp.py`, `smartmirror/content/routing.py`, `config.py`,
`sync.py`, `README.md`).

Committed as `8f3b159`.

## VERIFY (exact output)

**SDK content-sync daemon connects; all SDK tests pass** (against the
Dashboard repo's Mongo):
```
$ ./dev.sh up
dev.sh: content-sync: waiting for the first Mongo -> Qdrant reconcile...
dev.sh: content-sync: up (pid ...) -- dashboard edits now reach the RAG + widget cache live

$ CUDA_VISIBLE_DEVICES="" uv run pytest tests/ smartmirror/assistant/tests/ smartmirror/content/tests -q
159 passed in 95.51s
```
(One flaky run along the way: `test_assistant_answers_next_event_question`
failed once on the tiny `qwen2.5:0.5b` model giving a self-contradictory
answer -- "No, there are no upcoming events... the context provides
information about the Quantum Computing Crash Course event" in an earlier,
similar incident. Re-ran it alone immediately after and it passed; this is
pre-existing LLM-quality flakiness unrelated to the repo split, not a
regression -- the retrieval+prompt-block half of that same test, which
doesn't depend on the LLM's phrasing, passed every time.)

**Live loop across the repo boundary** -- created via the Dashboard repo's
API, read by the SDK's content sync, with no manual reconcile step:
```
$ curl -s -b cookies.txt -X POST http://localhost:8000/api/events -d '{...
    "title": "Cross-Repo Split Test Event", "status": "published", ...}'
{"id": "6ad4f809af7dd3831e1c6661", ...}
```
Within ~2s, the SDK's on-disk cache (read by a process in a *different*
repo on a *different* path) contained it:
```
found in live cache: True
Cross-Repo Split Test Event
```
Paused the daemon to safely query its Qdrant store directly, confirmed the
RAG side too:
```
- Event: Cross-Repo Split Test Event. Date: Tuesday, December 1, 2026 at
  11:00. Location: INSAT. Verifying the Dashboard repo and Smart-Mirror-SDK
  repo talk only through Mongo.
found: True
```
Deleted it via the Dashboard's API; gone from the cache within a few
seconds (first check raced the daemon's restart and showed a false
"still there" -- waited 5s, confirmed "still in cache after delete: False").

**Contract mismatch -- refuses, with a clear log line; recovers after
restoring it** (against the real, shared, non-test Mongo):
```
$ mongosh ... --eval 'db.getCollection("_meta").updateOne({_id:"contract"}, {$set:{version:"9.0"}})'
{ _id: 'contract', version: '9.0' }

$ ./dev.sh down && ./dev.sh up   # (Smart-Mirror-SDK)
...
$ tail .dev/logs/content-sync.log
2026-10-18 17:48:48,510 smartmirror.content.sync ERROR contract version mismatch: Mongo reports v9.0, this code expects v0.4 (major version differs) -- refusing to sync until this is fixed.

$ ./dev.sh status
Content sync:
  up (pid ...)
  last synced: None
  last error:  contract version mismatch: Mongo v9.0 vs code v0.4

$ mongosh ... --eval 'db.getCollection("_meta").updateOne({_id:"contract"}, {$set:{version:"0.4"}})'
$ ./dev.sh down && ./dev.sh up
$ ./dev.sh status
Content sync:
  up (pid ...)
  last synced: 2026-10-18 16:49:25.576000
  last error:  None
```

**`git status` clean in both repos** (confirmed just now, after all of the
above):
```
$ cd Smart-Mirror-SDK && git status --short
?? ui/      # pre-existing, unrelated -- see "Untouched, found as-is" above

$ cd Dashboard && git status --short
(nothing)
```

### Commits per repo

**Smart-Mirror-SDK** (`amin/content-sync`, new this session):
```
8f3b159 Split the dashboard out to the Dashboard repo; shrink this repo to the SDK side
```

**Dashboard** (`amin/fastapi-dashboard`, new this session):
```
8ea5114 Add dev.sh, infra/mongo (now owned here), and fix root-.env path depth
43ea886 Merge dashboard-export from Smart-Mirror-SDK (backend/, frontend/, full history)
e39a9fc Add ./dev.sh: one idempotent command for the whole dev stack          <- preserved history
c9739b8 Phase C (frontend): dashboard/frontend -- ...                         <- (subtree split,
e8de798 Phase C (backend): dashboard/backend -- ...                          <-  not new work)
06b27ae Initial commit                                                        <- pre-existing
```

## NEEDS YOU

**Push commands, in order** (I did not run these -- no git push without
being told to):

```bash
# 1. Dashboard repo first (SDK's tests/README now point at it, but nothing
#    there depends on SDK being pushed first -- order doesn't strictly
#    matter between the two, this is just a reasonable sequence)
cd ../Dashboard
git push -u origin amin/fastapi-dashboard

# 2. Smart-Mirror-SDK
cd ../Smart-Mirror-SDK
git push -u origin amin/content-sync   # if not already pushed from earlier sessions -- check first:
git log --oneline origin/amin/content-sync..HEAD   # anything listed hasn't been pushed yet
```

**Talk to the Dashboard repo's people before merging `amin/fastapi-dashboard` into its `main`.**
It currently has exactly one commit, by Moetez Fradi (also the
Smart-Mirror-SDK author) -- there's no competing implementation to
reconcile, but it's still *their* repo's `main` and first real code landing
in it; worth a heads-up/review before merging rather than just opening a
PR unannounced. There's no stack conflict to resolve (STEP 0 found nothing
to compare against), just the normal courtesy of a first PR into a
teammate's repo.

**Before anyone else runs either repo's `./dev.sh up` for the first time**,
note that `infra/mongo/.bin` (589M of mongod/mongosh binaries) and
`infra/mongo/.data` (411M, the live dev dataset) are gitignored -- they
exist only on this machine, copied from the original SDK location rather
than pushed. A fresh clone elsewhere re-downloads the binaries
automatically (`dev_mongod.sh`'s `ensure_binaries`) but starts with an
**empty** database until `seed-if-empty` runs its dev seed -- the actual
club content currently in the dataset on this machine does not travel with
the repos. If that content matters, it needs an explicit export/import
(e.g. `mongodump`/`mongorestore`) as a separate, deliberate step -- didn't
do this since nothing asked for it and it's a judgment call on your data,
not mine to make silently.

**Both repos' `.env` files hold live secrets** (admin passwords, JWT
secrets) -- confirmed gitignored in both, not committed, but flagging
since they now physically exist in two separate repo directories instead
of one.

## Decisions worth a second look (this session)

- **Subtree-split history vs. a fresh start**: chose to preserve the 3
  commits' authorship/messages via `git subtree split` + merge, per the
  explicit instruction. An alternative (copy the files, one fresh commit,
  reference the old history via a comment) would have been simpler but
  loses `git blame`/`git log` fidelity for that code going forward.
- **`backend/`/`frontend/` at the Dashboard repo's root, not under
  `dashboard/`**: there was no existing layout to defer to (STEP 0), and
  a repo whose entire purpose is the dashboard doesn't need the extra
  nesting. If the team already has a convention for this (e.g. matching
  some other repo's shape), this is the one thing from STEP 1 worth a
  quick sanity check before merging.
- **`infra/mongo/`'s small files (not `dashboard/`) were moved as new
  files, not subtree-split** -- wasn't asked to preserve their history
  specifically, and they're a handful of mostly-static config files where
  that would have added subtree-split complexity for little benefit.
- **The physical Mongo dataset was copied, not left to reseed from
  scratch** -- judgment call to avoid losing whatever had accumulated in
  it across sessions; see the NEEDS YOU note above about this not being a
  substitute for a real backup/migration of actual club content.
- **Contract-mismatch handling refuses the whole sync (reconcile *and*
  watch), not just one reconcile call** -- a version mismatch caught only
  at one `reconcile()` call but not gating `watch()` would have left the
  change-stream watcher running and silently applying a possibly-
  incompatible schema's writes to the cache/Qdrant every time something
  changed in Mongo, which seemed worse than just refusing outright until
  someone fixes the mismatch and restarts the daemon.
