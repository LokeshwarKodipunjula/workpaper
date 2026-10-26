# How I used AI on this case study

The brief says "use any tools you like, including AI; tell us how." Short version: the design, the stack, the review rules, the error list and every decision in [DECISIONS.md](DECISIONS.md) are mine. I used Claude Code as a fast implementer working from my plan and as a way to parallelise the first read of a 1.9 MB packet, and I treated its output the way I treat a junior's: useful, fast, and not to be trusted until I had read it.

## What was decided before any code was generated

- **The core idea.** A workpaper is a ledger of claims, not a grid of cells. Immutable packet, append-only event log, every number a node with provenance. The brief lists seven audiences, some of them years later. Seven audiences means "state at time T" has to be a first-class question, and that is event sourcing. Everything else in the design follows from that choice.
- **The stack.** FastAPI and Pydantic, SQLAlchemy over PostgreSQL (SQLite locally), WebSockets for presence and live updates, React with Vite, Docker, pytest. I limited myself to tools I use at work on purpose: I can only review generated code line by line in a stack I know, and I only want to defend technology in the interview that I actually use.
- **No LLM inside the product.** The brief never asks for one, and a CPA or an IRS examiner needs a trail that reproduces. Every check is deterministic and re-derives a figure from a second source. Where a model would plug in later (drafting client questions, narrating swings, reading real page images) is noted in the one-pager.
- **Review discipline as data.** Sign-offs bind to a fingerprint of their scope and reopen on change; client approval binds to the amounts presented; firm standards are editable data that the server enforces; an adjustment over the firm's threshold is proposed, not applied, until a partner approves.
- **The module boundaries.** `packet.py` (immutable input and indices), `events.py` (log and fold), `service.py` (read models), `checks.py` (independent checks), `records.py` (CPA records as views), `roles.py` (capability matrix), `main.py` (routes). The generator filled these in; it did not choose them.

## Where the tool did the typing, and how I checked it

- **Implementation.** Claude Code wrote the first cut of most modules and React pages from the module plan above, one module at a time with me reviewing between steps. I changed what I disagreed with: the area taxonomy, how the 302 lots collapse to exceptions, the masking boundary (one serialiser on the way out rather than per-route logic), and the permission matrix, which the first version duplicated in the UI and which is now served by the API so there is one copy. The pytest suite pins the rules I cared about, and the rules are what I reviewed most carefully.
- **Finding the planted mistakes.** I split the return into fourteen areas and ran one analysis pass per area with the instructions I would give a staff accountant: compare every extracted value with the printed page text, sum detail to totals, compare engine lines with their inputs and sources, cross-check documents that should agree, and compare the client's statements with the documents. The raw output is kept as `data/hunt_findings.json` (about 210 candidates). I then re-derived every high-severity candidate myself from the raw data (page text, extracted values, engine lines, agency records) before it became a check in `checks_targeted.py` or a row in [ERRORS_FOUND.md](ERRORS_FOUND.md). Candidates I could not confirm were dropped.
- **Verification.** Beyond pytest, a small Playwright script (`tools/shots.py`) screenshots every page as a given actor and prints console errors, so I could see a broken page in seconds instead of clicking through twelve routes.
- **Writing.** First drafts of these documents were generated from my notes and then rewritten by me.

## What I would not let it decide

Anything that changes what the workpaper means: what counts as evidence, when a sign-off is stale, who may do what, what gets frozen at filing, and which errors are real. Those are the judgment calls a reviewer relies on, and they are the ones I expect to be asked about.

## What I would do differently next time

Write the capability matrix, the event type list and the fingerprint rule down as a one-page spec before generating anything. The pieces that went smoothly were the ones with a written contract (the event types in the `events.py` docstring, the reference string formats in `packet.py`); the pieces I reworked were the ones where I let the first generated version define the rule.
