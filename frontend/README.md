# Workpaper UI

React 19 + Vite. No state library, no component kit: the server already projects the workpaper state, so the client is a thin set of pages over the API plus one context.

```
src/api.js                 fetch wrapper; sends X-Actor on every call, builds the WebSocket URL
src/context.js             the one React context (actor, overview, drawer, live tick)
src/App.jsx                shell: role picker, top bar with search and presence, side nav, drawer, routes
src/components/
  TracePanel.jsx           the trace drawer for a line: sources, build tree, downstream, history, actions
  DocumentViewer.jsx       page text with highlighted extracted values and the page map
  LinesTable.jsx           lines of an area/form, bulk select + verify
  forms.jsx                adjust / verify / note / ask / attach forms
  ui.jsx                   Chip, Ref, Who, Modal, useAsync and the status tone map
src/pages/                 one file per route (Overview, Area, Documents, Checks, Records, Activity,
                           Versions, Filing, Firm, ClientView, WhatIf, Household)
src/styles.css             plain CSS with design tokens
```

## How data flows

- Every page calls the API through `api.js` and re-fetches when `tick` in the context changes.
- `tick` increments on every WebSocket message from the server (someone adjusted, noted, signed off...). Re-fetching is deliberate: patching client state would duplicate the server's fold.
- If the WebSocket handshake never succeeds (serverless hosts such as Vercel), `App.jsx` falls back to polling `/api/heartbeat` every 3 seconds and bumps `tick` when the event sequence moves. Presence is empty in that mode; everything else behaves the same.
- Any reference string (`F1040.11`, `D31`, `ev-0498`, `doc:D31#page32`, `qa-14`, `py:/...`) goes through `openRef` in the context, which decides which drawer to open. That is what makes every number clickable.
- What the current actor may do comes from the server with the actor list (`capabilities`). The UI only uses it to hide buttons; the API enforces it.

## Run

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api and /ws to the backend on :8000
npm run build    # writes dist/, which FastAPI serves when present
npm run lint
```
