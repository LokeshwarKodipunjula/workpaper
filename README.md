# Miraflores Workpaper — Okafor-Lindqvist 2025

Case study submission by **Lokeshwar Kodipunjula** for the AI Engineer (Tax) role at MiraFlores AI, October 2026.

A web-native tax workpaper built from the purpose, not from a spreadsheet. The packet (74 documents, ~3,000 extracted values, three engine runs) is loaded as delivered and treated as immutable input. Everything the firm does on top of it — adjustments, verifications, notes, questions, sign-offs, assignments, time, views of sensitive data, filing events — is an append-only event log. The workpaper you see is a fold over that log.

- One page on the core idea and data model: [docs/ONE_PAGER.md](docs/ONE_PAGER.md)
- Errors found in the packet and how the design surfaced them: [docs/ERRORS_FOUND.md](docs/ERRORS_FOUND.md)
- Decision log (what I chose, what I rejected, why): [docs/DECISIONS.md](docs/DECISIONS.md)
- How I used AI while building: [docs/HOW_AI_WAS_USED.md](docs/HOW_AI_WAS_USED.md)
- Video walkthrough script: [docs/VIDEO_SCRIPT.md](docs/VIDEO_SCRIPT.md)

## Run it

**Docker (recommended, PostgreSQL included)**

```bash
docker compose up --build
# open http://localhost:8000
```

**Local, no Docker (SQLite)**

```bash
# backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# frontend (dev server with API proxy)
cd frontend
npm install
npm run dev          # http://localhost:5173
# or build once and let FastAPI serve it from frontend/dist:
npm run build
```

Set `DATABASE_URL` (e.g. `postgresql+psycopg://user:pass@host/db`) to use PostgreSQL; otherwise an SQLite file is created under `data/`. Set `PACKET_PATH` to load a different packet.

Pick a role on the first screen (or from the switcher in the top bar). As the firm administrator, **Firm → Replay the season** seeds the event log with the actions the firm took from January to the 2028 examination letter; **Reset** clears it.

## Tests

```bash
cd backend && pytest -q
```

## Layout

```
backend/app/packet.py    immutable packet model, provenance indices, reference resolver
backend/app/events.py    append-only event log + State projection (SQLAlchemy; SQLite or PostgreSQL)
backend/app/service.py   read models: line views, areas, variances, fingerprints, version compare
backend/app/checks.py    independent checks that do not trust the engine
backend/app/records.py   the records a CPA expects, generated from the graph
backend/app/roles.py     actors and server-enforced permissions
backend/app/seed.py      season replay for the demo
backend/app/main.py      FastAPI routes, WebSocket live updates (polling fallback via /api/heartbeat), static UI
api/index.py             Vercel entry point: the same app as one serverless function
frontend/src/            React UI (trace drawer, document viewer, areas, checks, records, filing, firm, client view)
```

## Engineering notes

Things worth knowing before reading the code:

- **The packet never changes.** `packet.py` loads it once and builds reverse indices (value → lines, document → lines, line → dependents). Swap the file and the firm's work in the event log is untouched.
- **State is a pure function of the log.** `State(events)` is rebuilt on each request. For one return that is a few hundred events and faster than a database round-trip; snapshotting is the first thing to add for a firm.
- **Rules live on the server only.** Permissions (`roles.py`) are checked on every mutating route and served to the UI with the actor list, so the React side has no copy to drift. The partner threshold is read from the firm's own rule text.
- **Masking is one choke point.** Every response for an actor without clearance passes through `mask_if_needed`; unmasked views of documents carrying identifiers are themselves events.
- **Checks never recompute tax.** Each one compares the engine with a second source (page text, supplement, paystub, transcript, closing statement, prior year). A check that throws reports itself as a warning and never hides the others.
- **Known gaps.** Schedule B payer lines are positional, so the 2024 comparison can pair the wrong payer; tax effects are the engine's per-dollar estimates, not a recompute; the static-file route serves `index.html` for anything outside `frontend/dist`.

`data/hunt_findings.json` is the raw candidate list from the packet analysis pass (see [docs/HOW_AI_WAS_USED.md](docs/HOW_AI_WAS_USED.md)); only confirmed items became checks.

## Deploy to a public link

**Vercel (no Docker)**

The repo deploys as one Python serverless function plus the static React build: `api/index.py` imports the FastAPI app, `vercel.json` builds the UI and rewrites `/api/*` to the function and everything else to `index.html`.

1. Push the repo to GitHub and import it in Vercel. No framework preset is needed; the settings are in `vercel.json`.
2. Add a Postgres database and set `DATABASE_URL` in the project's environment variables. Vercel's Marketplace (Neon, Supabase) or any hosted Postgres works; `postgres://` and `postgresql://` URLs are accepted as given. Without it the event log falls back to SQLite in the function's temp folder, which works for a demo but resets whenever the instance is recycled.
3. Deploy, open the URL, pick Jo Kimura and **Firm → Replay the season**.

Serverless hosts do not hold WebSockets open, so on Vercel the UI switches to polling automatically: the first failed WebSocket handshake starts a 3-second poll of `/api/heartbeat`, and any change in the event sequence triggers the same refetch a live event would. Presence avatars are the one feature that needs the socket and are hidden in that mode.

**Docker hosts (Render, Railway, Fly.io, AWS)**

The image is self-contained (packet + API + UI) and keeps the WebSocket. Any host that runs a Dockerfile works; with no `DATABASE_URL` it uses SQLite inside the container.

- **Render / Railway / Fly.io:** create a web service from this repo, Dockerfile build, expose port 8000. Add a PostgreSQL instance and set `DATABASE_URL` to keep the event log across restarts.
- **AWS:** `docker build -t workpaper .` then run on an EC2 instance or ECS with port 8000 open; point `DATABASE_URL` at RDS PostgreSQL.

After the first start, open the link, pick the firm administrator, and press **Replay the season** so every role has history to look at.
