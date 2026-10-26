# Start here

Prerequisites on the machine: **Python 3.11+** and **Node 20+** on PATH. Nothing else.

## Fastest: one command

Windows:

```bat
run.bat
```

macOS / Linux:

```bash
./run.sh
```

It installs the Python dependencies, runs `npm install` and `npm run build` in `frontend/`, and starts the server. Open <http://localhost:8000>.

## Step by step (same thing, by hand)

```bash
cd backend
pip install -r requirements.txt
cd ../frontend
npm install
npm run build
cd ../backend
python -m uvicorn app.main:app --port 8000
```

Open <http://localhost:8000>, pick a role, then as the administrator go to **Firm → Replay the season** to seed the demo data.

## Notes

- A prebuilt UI is already in `frontend/dist`, so if `npm install` is not possible the backend alone still serves the app. Rebuild only after changing files in `frontend/src`.
- For UI development with hot reload, run `npm run dev` in `frontend/` (port 5173, proxies to the backend on 8000).
- The event log is an SQLite file created at `data/workpaper.db` on first start. Delete it to start clean, or set `DATABASE_URL` for PostgreSQL.
- Tests: `cd backend && python -m pytest -q` (28 tests).
- To put it online: push to GitHub and import in Vercel (settings are in `vercel.json`; set `DATABASE_URL` to a Postgres URL for a log that survives redeploys), or use the Dockerfile on Render / Railway / Fly.io. Details in the README under "Deploy to a public link".
