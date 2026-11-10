# Overnight report -- `amin/content-sync`

Ran unattended overnight (2026-10-08 -> 2026-10-10). All work is committed on this
branch in 4 commits (list at the bottom). Nothing was pushed or merged.

## Phase A -- Local Mongo: **done**

`docker ps` failed with permission denied -- the `docker` group exists (gid 1001)
but this user isn't a member of it, so I used the tarball fallback instead of
sudo, per your instructions.

- Downloaded MongoDB 7.0.43 (`ubuntu2204` build -- there is no `ubuntu2404`
  build for the 7.0 line; this machine is actually Ubuntu 26.04, and the
  ubuntu2204 binaries run fine on it) and mongosh 2.13.0 into
  `infra/mongo/.bin/` (gitignored).
- `infra/mongo/dev_mongod.sh {start|stop|status|init|seed}` runs it as a
  single-node `rs0` replica set, data in `infra/mongo/.data/` (gitignored).
  **It's running right now** (started during this session) -- `./infra/mongo/dev_mongod.sh status`
  to check, `stop` to kill it.
- `infra/mongo/CONTRACT.md`, `init_db.js`, `seed.js`, `docker-compose.yml` were
  already on disk but **not yet committed to git** -- I committed them
  alongside my own additions.

### Verification (`infra/mongo/verify_phase_a.py`, exact output)

```
=== a) countDocuments per collection (vs seed.js) ===
  events: expected=4 got=4 OK
  announcements: expected=2 got=2 OK
  about: expected=2 got=2 OK
  achievements: expected=1 got=1 OK
  board: expected=2 got=2 OK

=== b) inserting an invalid doc into events is REJECTED ===
  OK: insert rejected -- Document failed validation ... missingProperties:
  ['created_at', 'description', 'start', 'status', 'title', 'updated_at', 'updated_by']

=== c) change stream receives a 'delete' operationType ===
  OK: got delete event -- documentKey={'_id': ObjectId('...')}

=== d) re-running init_db.js is idempotent ===
  stdout: ok: events / ok: announcements / ok: about / ok: achievements / ok: board
  OK: exit code 0, counts unchanged=True

=== SUMMARY ===
{ "all_checks_passed": true }
```

(c) was done in `verify_phase_a.py`/`phase_a_verify.py`, a real Python script with
pymongo, not an interactive shell, per your instruction.

## Phase B -- Mirror content sync (`smartmirror/content/`): **done**

New package: `config.py`, `templates.py`, `routing.py`, `cache.py`, `indexer.py`,
`sync.py`. Opt-in via `MONGO_URI` -- unset, the mirror behaves exactly as before
(seed corpus, no club widgets). Reuses the assistant's existing
Chunker/Embedder/VectorStore rather than a second RAG stack; those three got
small additive extensions (optional `ids=` and `delete_by_source()`/`clear()`
on `VectorStore`, a `split()` on `Chunker` for in-memory text) -- nothing in
`rag/` lost backward compatibility. `Assistant` got two new optional
constructor args, both defaulting to `None` (`store`, `extra_context`), so it
can point at the Mongo-derived Qdrant collection and get the live
events/announcements/mission prompt block without knowing anything about Mongo.

Wiring is in `server/app.py` (`content_sync=` param, gathered alongside the
main loop) and `examples/mvp.py` only (builds `ContentSync` when `MONGO_URI` is
set, feeds it to the assistant and the Events widget) -- did not touch
`SMARTMIRROR_MONGO_READ_URI`, the unrelated personal-calendar Mongo wiring
that was already there.

`mirror_status` added to the contract (bump to v0.2) -- written by the mirror
every 30s, read by the dashboard, exempt from the common status/created_at
fields since it isn't board content.

**Real bug caught and fixed before committing**: the heartbeat loop originally
did `await asyncio.sleep(30)` with no way to wake early, so `server.stop()`
could hang up to 30s. Fixed with a step-sleep that checks the stop event every
0.5s (`ContentSync._sleep_or_stop`).

### Tests: 33 new, all passing

Run: `./infra/mongo/dev_mongod.sh start && uv run pytest smartmirror/content/tests -q`

Covers: insert/update/delete -> cache + Qdrant; published->draft removed;
draft never indexed; expired announcement / past event hidden from the widget
but still retrievable (RAG); offline-gap reconcile; invalid resume token ->
full reconcile; embedding-model-mismatch -> full rebuild; Mongo-down doesn't
raise; heartbeat upserts `mirror_status`; prompt-block assembly.
`assistant.chat("What is the next event?")` was exercised for real against the
local Ollama (`qwen2.5:0.5b`) already running in this environment and
correctly answered with the seeded event title; a retrieval+prompt-block
check (no LLM needed) always runs alongside it, per your "if no LLM available"
fallback instruction -- in this case the LLM *was* available, so both ran.

## Phase C -- Dashboard (`dashboard/`): **done**

**Backend** (`dashboard/backend`, its own uv project/venv -- didn't want to pull
torch/mediapipe into the dashboard's environment): FastAPI + pymongo, bcrypt
password hashes in `dashboard_users`, stateless JWT session in an httponly
cookie (not a server-side session store), roles `admin`/`editor`. Generic CRUD
router factory instantiated once per collection (list/get/create/put/delete +
publish/unpublish). Server always sets `created_at`/`updated_at`/`updated_by`;
Mongo's own `$jsonSchema` rejection is mapped to a clean 422. `langdetect`
English check on long text fields, returned as non-blocking `warnings`.
Every write is logged to `audit_log`. `GET /api/mirror/status` with the
online-if-seen-in-90s flag. `dashboard_users` and `audit_log` added to the
contract (bump to v0.3), both documented as mirror-never-reads.

**Frontend** (`dashboard/frontend`, React 19 + TypeScript + Vite 7, dev port
5174 so it never collides with the mirror's own frontend on 5173): no UI
framework, no router -- a sidebar sets which section is shown. One
`FieldSchema[]` config per collection drives both the list and the
create/edit form. Africa/Tunis <-> UTC conversion is a fixed +1h offset
(Tunisia has had no DST since 2009), not a timezone database. Publish/unpublish
toggle, delete-with-confirm, and the mirror status page (auto-refetch 10s).

### Tests & verification

- Backend: `uv run pytest tests -q` inside `dashboard/backend` -> **18
  passed** (auth, full CRUD + publish toggle, server-sets-fields-not-client,
  Mongo validation -> 422, audit log ordering, English-warning + short-text
  skip, mirror online/offline).
- Also smoke-tested as a real running `uvicorn` process against the actual
  dev `ieee` database (login, create, list, delete, mirror status) -- all
  worked; the test event was deleted afterward (counts above are back to the
  original seed numbers).
- Frontend: `npm run build` (`tsc -b && vite build`) -- **0 TypeScript
  errors**. Ran both dev servers together and verified the CORS
  preflight + credentialed-cookie login from `http://localhost:5174` against
  the backend works exactly as the browser's `fetch(..., {credentials:
  'include'})` calls in `api.ts` would do it.
- **Gap, stated plainly rather than glossed over**: I did not click through
  the actual rendered UI in a browser. This environment has Brave/Firefox
  installed but no Claude-in-Chrome session configured, and setting one up
  felt like the wrong unattended-overnight risk to take. Please sanity-check
  the UI yourself the first time (`npm run dev` in `dashboard/frontend` +
  `uvicorn app.main:app` in `dashboard/backend`) before trusting it fully --
  the API surface it depends on is tested, the component logic is
  straightforward (list/form/toggle), but I can't promise there isn't a CSS
  layout issue or a click that doesn't do what it looks like it should.

## Credential I created during testing -- rotate this

While smoke-testing the backend against the real dev `ieee` database, I ran
`scripts/create_admin.py` and created:

- **username:** `admin`
- **password:** `supersecret123`

in your actual local `dashboard_users` collection. This is a throwaway dev
credential, not a secret I'm trying to hide, but you should either change the
password or re-run `create_admin.py` before relying on it.

## NEEDS YOU

In order:

1. **Docker group** (so `docker compose` works instead of the tarball
   fallback). The group already exists on this machine, you're just not in
   it yet:
   ```
   sudo usermod -aG docker $USER
   ```
   then log out and back in (or open a new terminal/`newgrp docker`) for the
   group membership to take effect. After that, `infra/mongo/docker-compose.yml`
   works as originally written (`cd infra/mongo && docker compose up -d`) if
   you'd rather use that than the tarball `dev_mongod.sh`.

2. **Firewall for the Pi** (only needed once the Pi needs to reach this PC's
   Mongo over LAN -- not needed for anything I ran tonight, which was all
   localhost):
   ```
   sudo ufw allow from 192.168.0.0/16 to any port 27017
   ```
   adjust the subnet to your actual LAN. You'll also need to change
   `dev_mongod.sh`'s `--bind_ip 127.0.0.1` to `--bind_ip 0.0.0.0` (or the PC's
   LAN IP) -- I deliberately left it bound to localhost-only since there's no
   Mongo auth configured yet, and opening it to the LAN unauthenticated is a
   call you should make, not me.

3. **Rotate the `admin`/`supersecret123` dev credential** mentioned above
   (or just re-run `create_admin.py` with a real password).

4. **Set a real `DASHBOARD_JWT_SECRET`** before trusting the dashboard with
   real sessions -- right now it falls back to a random per-process secret
   if unset (safe but logs everyone out on every backend restart). Put it in
   `dashboard/backend/.env` (see `.env.example`).

5. **Click through the dashboard UI yourself once** (see the Phase C gap
   above) -- the one thing I couldn't verify.

## How to run each piece

**Mongo** (already running -- this is for next time / another machine):
```
./infra/mongo/dev_mongod.sh start     # or: cd infra/mongo && docker compose up -d
./infra/mongo/dev_mongod.sh init       # idempotent
./infra/mongo/dev_mongod.sh seed       # dev-only fictional data, wipes first
./infra/mongo/dev_mongod.sh status
./infra/mongo/dev_mongod.sh stop
```

**Mirror, with the Mongo content sync enabled:**
```
MONGO_URI="mongodb://localhost:27017/ieee?directConnection=true" uv run python examples/mvp.py
```
(unset `MONGO_URI` for the old behavior -- seed corpus, no club widgets.)

**Dashboard backend:**
```
cd dashboard/backend
cp .env.example .env   # edit DASHBOARD_JWT_SECRET at least
uv run python scripts/create_admin.py <username> <password>   # first admin
uv run uvicorn app.main:app --reload --port 8000
```

**Dashboard frontend:**
```
cd dashboard/frontend
npm install
npm run dev     # http://localhost:5174, talks to localhost:8000 by default
                 # override with VITE_DASHBOARD_API_URL if the backend is elsewhere
```

**Full combined test suite** (I found the GPU on this machine -- a 2GB MX550 --
intermittently OOMs when many `SentenceTransformer` loads stack up in one long
pytest process; harmless, just run with CUDA disabled):
```
CUDA_VISIBLE_DEVICES="" uv run pytest tests/ smartmirror/assistant/tests/ smartmirror/content/tests -q
cd dashboard/backend && uv run pytest tests -q
cd dashboard/frontend && npm run build
```

## Decisions I made that you should review

- **`uv run pytest` was silently running the wrong environment for part of
  this session.** `pytest` (and `pytest-asyncio`, see below) were never
  actually installed in `.venv` by a plain `uv sync` -- they're dev-extra-only
  and `uv run <cmd>` doesn't pull in extras unless you pass `--extra`. Plain
  `uv run pytest` was falling back to a `pytest` found elsewhere on `$PATH`
  (miniconda's), which happened to *also* have enough packages installed to
  pass some tests, making the problem very easy to miss. I fixed it locally
  by running `uv sync --extra dev --extra assistant --extra data` once, but
  that's a workaround, not a fix to the project: consider adding
  `[tool.uv] default-groups = [...]` to `pyproject.toml`, or just document
  `uv sync --all-extras` in the README, so this doesn't bite someone else.
- **Added `pytest-asyncio` to the `dev` extra** -- `smartmirror/assistant/tests`
  uses `@pytest.mark.asyncio` but the package was never declared as a
  dependency anywhere. It must have been present ambiently in whatever
  environment last ran these tests clean.
- **`mirror_status`, `dashboard_users`, and `audit_log` are exempt from the
  contract's common status/created_at/updated_by fields.** They don't have a
  draft/published lifecycle and aren't board-authored content, so forcing
  them through `ensure()`'s schema didn't make sense -- each gets its own
  validator in `init_db.js` instead, documented as an explicit exemption in
  `CONTRACT.md`.
- **Dashboard sessions are a stateless JWT cookie, not a server-side session
  store.** Simpler, no session collection to manage, but it means there's no
  way to force-revoke a session before it expires (8h default) short of
  rotating `DASHBOARD_JWT_SECRET` (which logs everyone out). Fine for a small
  exec board; reconsider if that ever matters.
- **No admin-only "create another user" API endpoint** -- only the CLI
  (`create_admin.py`) creates dashboard users, as the task asked for. If the
  exec board turns over and multiple people need logins without you running
  the CLI each time, that's the next thing to add.
- **No dedicated Announcements widget.** `smartmirror/content/sync.py`'s
  `widget_data("announcements")` is implemented and tested, but there's no
  `AnnouncementsWidget` class/frontend component to show it on the mirror
  (only `EventsWidget` existed already and is wired up). Adding one is a
  small, separate piece of work I didn't do since it wasn't explicitly asked
  for and touches the frontend widget registry.
- **`langdetect`'s English check has false positives on short, unremarkable
  sentences** (saw it flag "Verifying the real running server end to end." as
  Norwegian during smoke-testing). It's advisory-only by design per your
  spec ("return a warning, don't block"), but don't take the warning text as
  gospel.
- **Left `infra/mongo/docker-compose.yml` untouched** even though the
  tarball fallback is what's actually running -- once the docker group fix
  lands, `docker compose up -d` should work as originally written against the
  same `init_db.js`/`seed.js`.

## Open questions for you

- Is a stateless JWT cookie (vs. a revocable server-side session) actually
  fine for this use case, or do you want sessions you can kill immediately?
- Do you want an Announcements widget on the mirror, or is the voice
  assistant (which does get announcements in its prompt block) enough for now?
- Is `editor` meant to have any restriction relative to `admin` beyond
  "can't create other users via the CLI"? Right now both roles can do
  anything to content -- the role is tracked and returned by the API but
  nothing currently branches on it.

## Untouched, found as-is

- `ui/` at the repo root: an untracked, unrelated `node_modules/` (111MB, no
  visible `package.json` at that level) with no connection to anything in
  this task. Didn't touch it -- flagging in case it's abandoned work you want
  to clean up, or in-progress work you don't.

## Commits on this branch (`amin/content-sync`)

```
68c48a1 Phase A: local Mongo dev setup (replica set, no docker/sudo)
d0c9d9e Phase B: smartmirror/content/ -- Mongo -> cache + Qdrant sync, opt-in via MONGO_URI
0341ce1 Phase C (backend): dashboard/backend -- FastAPI CRUD + auth + mirror monitoring
ffd5dbf Phase C (frontend): dashboard/frontend -- React + TypeScript + Vite exec-board UI
```

Nothing pushed, nothing merged, nothing force-anything. `git log ba70055..HEAD`
to see the same list with `ba70055` (the branch point) as the base.
