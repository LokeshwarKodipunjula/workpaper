# Decision log

Short records of the choices that shape this workpaper: the ten that set the design, then the engineering choices underneath them. Each one says what I decided, what I rejected, and why. Lokeshwar Kodipunjula, October 2026.

## 1. Treat the packet as immutable input
**Decision.** Load the packet JSON as delivered, build indices in memory, never edit it.
**Rejected.** Importing it into relational tables and letting users correct values in place.
**Why.** The brief says the packet contains confident mistakes and that real documents will replace the simulated ones. If corrections live in the packet, swapping the packet loses them. Keeping corrections outside the packet (as events) means the pipeline output can be replaced wholesale and the firm's work survives.

## 2. Everything the firm does is an append-only event
**Decision.** One `events` table; the workpaper state is a fold over it. Undo appends a compensating event. Bulk actions share a batch id.
**Rejected.** Mutable rows for notes, adjustments and sign-offs with an audit table on the side.
**Why.** Seven audiences, some of them years later. "What changed since I last looked", version compare, the frozen filed record, the notice response and next year's roll-forward are all "state at time T". With an event log they are one function; with mutable rows they are five features that drift.
**Tradeoff accepted.** State is rebuilt per request. Fine for one return; a firm would snapshot per client.

## 3. Sign-offs bind to a content fingerprint
**Decision.** A sign-off stores a hash of every effective value in its scope. When a value in scope changes, the system appends `signoff.reopened` with the cause. Client approval stores the fingerprint of the amounts presented and e-file is refused if it no longer matches.
**Rejected.** Manual "withdraw sign-off" and a reminder.
**Why.** The packet's own timeline shows the failure mode: the client signed on v3 while three later facts were in hand. The rule has to be mechanical.

## 4. Firm standards are data, and the server enforces them
**Decision.** Variance thresholds, verification types, rules and required steps come from the packet's starter standards with overrides stored as events. Permissions are a capability matrix checked on every mutating route.
**Rejected.** Hard-coding the rules; enforcing in the UI only.
**Why.** The administrator role must be able to change standards firm-wide, and a role switcher in the UI is not a security boundary.

## 5. Checks re-derive, they do not re-compute
**Decision.** Each check compares the engine with a second source: page text vs extracted value, supplement vs broker basis, paystub vs W-2 box 16, IRS transcript vs client answer, closing statement vs tax bill, 2024 return vs organizer.
**Rejected.** Re-implementing the tax engine to recompute lines.
**Why.** The brief says results are computed for us and the engine cannot be rerun. Independent evidence catches what a recompute from the same inputs would repeat. Tax effects of corrections use the engine's per-dollar rates, as the README instructs, and the UI says they are estimates.

## 6. Large detail collapses to exceptions first
**Decision.** The 302 Form 8949 lots show totals by box and broker plus the lots with flags (zero basis, holding period vs box, adjusted, engine note, California-source). Every lot is one click away.
**Rejected.** Paging through all lots.
**Why.** "Handle large detail without swamping the review." A reviewer wants the ones that can be wrong.

## 7. No LLM in the product
**Decision.** No model calls at runtime. AI was used to build and to analyze (see HOW_AI_WAS_USED.md).
**Rejected.** A chat panel over the return.
**Why.** The brief does not ask for one, and the users need reproducibility. The data model leaves room for it later (questions, notes, extracted values with confidence).

## 8. Stack
**Decision.** Python, FastAPI, Pydantic, SQLAlchemy, PostgreSQL (SQLite for local), WebSockets, React with Vite, Docker, pytest.
**Rejected.** Streamlit or Gradio for the UI.
**Why.** The bar is "faster and more trustworthy than anything a 20-year CPA has used"; that is a product, not a dashboard. These are tools I know well enough to review generated code line by line. I first ruled out serverless hosts because WebSockets need a long-running process; that changed when the UI gained a polling fallback (decision 28), so the primary deploy is a Docker host and Vercel is a supported second path with presence turned off.

## 9. Simulated documents that real images can replace
**Decision.** A page is rendered from `printed_content` with the extracted values highlighted in the text, plus a page map placing the synthetic position boxes. The value-to-line links hang off the extracted value id, not the rendering.
**Why.** The brief asks that real source documents replace the simulated ones seamlessly. Only the renderer changes.

## 10. Areas follow the firm's budget
**Decision.** Lines and documents are classified into the firm's eight budget areas plus "retirement and HSA", "payments and filing" and "return summary" (California is already a budget area; partner review is a budget line but not an area of the return). Area status is derived (blocked, open items, prepared, reviewed, signed).
**Why.** Time against budget, assignments and sign-offs all need the same unit, and the firm already thinks in those areas.

## 11. Identity is a header, permissions are a matrix
**Decision.** Every request carries `X-Actor`; the server resolves it to a staff member, client user or the examiner and checks a capability matrix (`roles.py`) on every mutating route. The role switcher only changes the header.
**Rejected.** Real authentication (OAuth, sessions) for the prototype; permission checks in the React components only.
**Why.** The brief asks for a role switcher, not a login. Putting the matrix server-side means the switcher is a demo convenience and the rules still hold if someone calls the API directly. Swapping the header for a session cookie later touches one dependency (`current_actor`).

## 12. Sensitive data is masked at the serialization boundary, and the unmask is the logged event
**Decision.** For actors without clearance, every response passes through one masker that redacts SSNs, EINs, account numbers and PINs by pattern. For cleared actors, opening a document that carries identifiers appends a `view.sensitive` event.
**Rejected.** Separate "masked" and "unmasked" endpoints; masking in the UI.
**Why.** One choke point cannot be forgotten by a new route. Logging the view rather than the request matches the firm rule as written ("every unmasked view is logged").

## 13. Reference strings are the universal link
**Decision.** Every provenance pointer in the system is a string in the packet's own formats (`ev-0498`, `D31`, `doc:D31#page32`, `qa-14`, `py:/basis_records/...`, `agency:/efile/0`, `asset:SAC-BLDG`, `household:theo`, `ref:fx.SEK.2025_average`, `F1040.11`). One resolver turns any of them into a typed node; one UI component turns any of them into a link that opens the right drawer.
**Rejected.** Foreign keys per type and a different component per type.
**Why.** Checks, notes, adjustments, questions and records all need to cite evidence of any kind. A single format means evidence can be typed by a human in an adjustment form and still resolve.

## 14. Tax effect by category, not by recompute
**Decision.** Each line key maps to one of the engine's rate categories by a prefix table (`service.py`); an adjustment's effect is the change times the per-dollar rate, and payments and credits move the balance one-for-one. The partner threshold applies to the larger of the federal and California effect.
**Rejected.** Letting the user pick a rate freely; re-running any tax logic.
**Why.** The README defines this method and says the real system recomputes. The category is shown and overridable on the form, and the UI labels every effect as an estimate.

## 15. State is projected per request; the event cache lives in memory
**Decision.** `State(events)` is rebuilt on each request from an in-process list that the store appends to. No snapshots, no materialized views.
**Rejected.** Incremental projections or a CQRS read model.
**Why.** One return has a few hundred events; folding them costs less than a database round-trip. The projection is a pure function, which is what makes it testable and what makes replay (the seed, version compare, the frozen record) trivial. Snapshotting is the first optimization when this serves a firm.
**Later amendment.** The cache now compares its last sequence number with `max(seq)` in the database before it is used, so several processes (or serverless instances) sharing one database never serve a stale fold (decision 28).

## 16. Live updates through a single in-process hub
**Decision.** FastAPI's WebSocket endpoint keeps the connected clients with their actor and current view; every write broadcasts the event and presence. The UI refetches on each event rather than patching state.
**Rejected.** Redis pub/sub; pushing full state diffs.
**Why.** One process serves one firm's demo; adding Redis buys horizontal scale the prototype does not need, and the hub class is written so the broadcast could be swapped. Refetch-on-event keeps the client simple and correct, at the cost of a few extra reads. Where no process can hold a socket (serverless), the client polls the event sequence instead and the same refetch runs (decision 28).

## 17. Undo is a compensating event, and bulk actions share a batch id
**Decision.** `undo` records the undone event id or batch id; the fold skips undone events. Nothing is deleted. A person can undo their own actions; partners and the administrator can undo anyone's.
**Why.** "Act on many items at once, with undo" plus an audit trail that an examiner can trust are only compatible if undo is itself recorded.

## 18. Checks are small functions behind one decorator, with human overrides
**Decision.** Each check is a function registered with `@check` that returns rows with a stable id, an area, a status, a message, refs and a suggested action. Reviewers can accept or waive a check with a reason; the override is an event and the raw status is kept. Checks whose target line has a proposed correction downgrade to a warning that says so.
**Rejected.** A rules DSL; a single monolithic validation pass.
**Why.** Adding a check is adding a function, which is what happens after every season. A broken check reports itself and never hides the others.

## 19. The filing lifecycle is a guarded state machine
**Decision.** Statuses: open, in review, partner approved, sent to client, client approved, extension filed, e-filed, rejected, accepted (frozen), amending, amended filed. Gates are enforced server-side: partner sign-off and no blocking notes before the client sees it; client approval with a matching fingerprint before e-file; no adjustments once frozen unless an amendment is open, and then they carry an `amendment` layer tag.
**Why.** The brief's "freeze at filing; amend on top" and "sign-offs that reopen" are invariants, and invariants belong in the transition function, not in the UI.

## 20. The packet stays in memory with indices, not in tables
**Decision.** The packet is parsed once at startup into dictionaries plus reverse indices (value to lines, document to lines, line to dependents) and searched linearly.
**Rejected.** Loading documents, values and lines into PostgreSQL.
**Why.** 1.9 MB, immutable, replaced as a whole. Indices in memory are simpler and faster than joins at this size, and search over 3,000 values takes milliseconds. For many clients the index moves to PostgreSQL full-text search and the resolver interface does not change.

## 21. One container, FastAPI serves the built UI
**Decision.** A two-stage Dockerfile builds the Vite bundle and copies it into the Python image; FastAPI mounts the assets and falls back to `index.html` for client routes. SQLite inside the container by default, PostgreSQL by `DATABASE_URL`.
**Rejected.** Separate frontend and backend deployments behind a proxy.
**Why.** "Run from a link" with the fewest moving parts; same origin avoids CORS and WebSocket proxy configuration on the host. The Vercel path (decision 28) keeps the same single origin: static build plus one function behind rewrites.

## 22. Tests target the rules, not the pages
**Decision.** The pytest suite exercises the provenance graph (every cited source resolves, every input exists), the fold (undo, batch undo, fingerprints), and the firm rules through the HTTP layer (threshold routing, cannot review own work, blocking notes, judgment needs authority, client-only answers, freeze and amend, signature voided by change, masking and view log, standards changing what checks flag, the planted identity error). UI verification was done by screenshotting every page in headless Chromium and reading the console.
**Why.** The rules are the product; the pages change weekly. Tests that pin the rules let the UI move freely.

## 23. Prior-year comparison by shared line keys with an explicit remap
**Decision.** The 2024 return's lines share keys with 2025 where the form did not change; a small table remaps the ones that moved (the 2024 Form 540 lines to 540NR). Variance uses the firm's threshold (both percent and amount) and is explained by a note of kind `variance`.
**Rejected.** Fuzzy matching by label.
**Why.** Line keys are the stable identity the engine already uses; label matching would silently pair the wrong lines (Schedule B payer lines are positional, which is the known gap).

## 24. React with context and fetch, no state library
**Decision.** One context carries the actor, the overview, the open drawer and a tick that increments on every live event; pages call the API through a thin client and refetch when the tick changes. Plain CSS with design tokens.
**Rejected.** Redux or a query cache; a component library.
**Why.** The server is the source of truth and already projects state; duplicating it on the client invites drift. Fewer dependencies also means fewer things to explain on review.

## 25. Seeded season replay instead of fixtures
**Decision.** A seed script replays the packet's own timeline as events with their original dates (assignments, verifications, the corrected 1099 reopening a sign-off, the extension, client questions and answers, the corrections of the engine's mistakes, judgment notes), so every role has history on first open. Reset clears it; the packet is never touched.
**Why.** "Replay the season" is itself a feature the brief asks for, and it doubles as a living integration test of the event types.

## 26. The UI never has its own copy of the rules
**Decision.** The capability matrix lives in `roles.py` only; `/api/meta` returns each actor with their `capabilities`, and the React `can()` helper reads that list. The partner threshold is parsed from the firm's rule text (`partner_threshold`), not hard-coded in two places.
**Rejected.** A mirrored permissions object in `App.jsx` (the first version had one).
**Why.** The two copies had already drifted: the server knew the `carryforward` capability and the client's copy did not. One source of truth means a standards change or a new role is one edit, and the UI can only ever be more restrictive than the API by accident, never less.

## 27. The partner's queue lives on the Filing page
**Decision.** The overview response carries `pending_adjustments` (every proposed adjustment over the firm's threshold), and the Filing page lists them with Approve / Reject next to a **Partner sign-off on the whole return** button. The server refuses that sign-off while any remain, and refuses "Send to client" without it.
**Rejected.** Leaving approval inside each line's trace drawer only.
**Why.** Rehearsing the walkthrough against the API showed the gate could not be cleared from the UI at all: the whole-return sign-off existed as a server rule but no page could give it, and the eight proposed corrections after the season replay had to be hunted down area by area. The partner's last step before filing is "what is still waiting for me", so that list belongs where filing happens. The test suite now covers the gate end to end.

## 28. One codebase for a long-running server and for serverless
**Decision.** The same FastAPI app runs under uvicorn (Docker, local) and as a single Vercel Python function (`api/index.py`). Three things made that possible without forking the code: the store normalises any Postgres URL and falls back to the instance temp folder when the project directory is read-only; the per-process event cache checks `max(seq)` before trusting itself, so two instances sharing one database stay consistent; and the UI treats a failed WebSocket handshake as "this host has no sockets" and polls a `/api/heartbeat` sequence number instead.
**Rejected.** Splitting the UI onto Vercel and the API onto a Docker host (CORS, two deploys, nothing gained for the demo); dropping live updates entirely on serverless.
**Why.** The reviewer should be able to open a link, and a free Vercel deploy from a GitHub repo is the lowest-friction way to give them one. The polling fallback was verified in a headless browser with WebSockets disabled on the server: the heartbeat fires every 3 seconds and a change made through the API refetches the overview on the next beat. The cache check also fixed a latent bug that any multi-worker deployment would have hit.
