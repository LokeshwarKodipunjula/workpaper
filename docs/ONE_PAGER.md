# The core idea and the data model

Lokeshwar Kodipunjula · MiraFlores AI case study · October 2026

## Core idea: a workpaper is a ledger of claims, not a grid of cells

A spreadsheet stores values. A workpaper has to prove them. So the unit of this system is not a cell but a **claim with provenance**: every number on the return is a node that knows where it came from, how it was built, what depends on it, who checked it and how, what was done to it, and what is still open.

Two facts follow from that and shape everything else:

1. **The packet is immutable input.** Documents, extracted values, client answers, prior years, agency records and the three engine runs are loaded as delivered and never edited. Real source documents replace the simulated ones by swapping one renderer; the highlight boxes and value-to-line links stay.
2. **Everything the firm does is an append-only event.** Adjustment, verification, note, question, answer, attachment, sign-off, assignment, time, sensitive-data view, standards change, filing step, client approval, undo. Nothing is updated in place; undo appends a reversal; a bulk action shares a batch id so one undo reverses it. The workpaper you see is a fold over the event log at any moment, which is what makes "since I last looked", version compare, the frozen filed record, the notice response and next year's roll-forward the same mechanism rather than features.

The review discipline comes from binding people to content. A **sign-off stores a fingerprint** of every effective value in its scope; when any of those values changes, the sign-off is reopened by the system with the cause recorded. A **client approval stores the fingerprint of the amounts presented**; e-file is refused unless it still matches. Firm standards are data (variance thresholds, verification types, rules, required steps) and the server enforces the ones that can be enforced: a preparer cannot block, a reviewer cannot sign work they prepared, a judgment call must cite its authority, an adjustment with more than 1,000 of tax effect is proposed, not applied, until a partner approves it.

**Checks don't trust the engine.** Each one re-derives a figure from a second place (the page text, a supplement, a paystub, the IRS transcript, a closing statement, the prior-year return, a client's statement) and compares. Big detail is handled by aggregation with exceptions first: 302 Form 8949 lots collapse to totals by box and broker plus the lots with flags.

## Data model

```
PACKET (immutable)                              EVENT LOG (append-only)
  Document ─┬─ Page(printed_content) ─┐           Event{seq, at, actor, role, type, target, area,
            └─ ExtractedValue ─────────┤                 batch_id, undo_of, payload}
                 {field, value, text_as_read,      types: adjustment.proposed/approved/rejected
                  position, confidence}            │      verification.recorded  note.created/resolved/
  ReturnVersion(v1..v3) ─ Line ────────┤           │      reopened/replied  question.asked/answered
       {key, form, jurisdiction, value, │           │      attachment.added  signoff.given/reopened
        rule, inputs[], sources[], note}│           │      assignment.set  time.logged  view.sensitive
  ClientAnswer / Message / CallNote ───┤           │      standards.updated  filing.status
  PriorYear(lines, assets, basis, carry)│           │      client.approval  read.marker  check.override
  AgencyRecord(transcript, FTB, efile, │           │      whatif.saved  carryforward.noted  undo
                notices) ──────────────┤           ▼
  Firm(staff, standards, budget) ──────┘        STATE = fold(events)
                                                  adjustments by line (effective value = last applied)
         any of these is a REF string             verifications, notes, questions, attachments,
   (ev-NNNN, D01, doc:D31#page32, qa-14,          signoffs{scope, level, fingerprint, status},
    py:/pointer, agency:/pointer, asset:ID,        assignments, time, view log, standards overrides,
    household:id, ref:param.x, F1040.11)           filing status + history, client approvals,
                                                  read markers, check overrides, what-ifs
```

**Provenance graph.** Lines point down to other lines (`inputs`) and to leaf references (`sources`). Indices give the reverse edges: value → lines citing it, document → lines, line → dependents. From that graph come the trace drawer (how built, where it flows), "where a document landed", version diffs, and the related-return links.

**Areas** are a classification over lines and documents (the firm's eight budget areas plus retirement and HSA, payments and filing, and the return summary). Area status is derived: blocked (failing check or blocking note) → open items → prepared → reviewed → signed.

**Line view** = engine line + effective value + adjustments + verifications + notes + questions + attachments + variance vs 2024 + category for tax-effect estimation (the engine's per-dollar rates).

**Records** (summary vs last year, tax computation, area summaries, document index, depreciation by asset, sales detail, books-to-tax, rentals, K-1 and basis, retirement and foreign, deductions with limits, payments, state split, carryovers, basis by year, prior preparer vs us, completeness, judgments, sign-offs, notice response, carry-forward plan) are views over the graph and the state, never stored.

**Roles** are server-enforced capabilities on actors (firm staff, client users, an examiner). Clearance masks identifiers and logs every unmasked view.

**Storage.** Packet in memory with indices; events and attachments in PostgreSQL (SQLite for local dev) through SQLAlchemy. FastAPI serves the API, a WebSocket for presence and live events, and the built React UI. Replacing the packet or the engine means replacing one file; the event log and everything derived from it stay.

## Why this beats the spreadsheet for both users

The 20-year CPA gets a workpaper where trust is visible: every number has its page, its rule, its checker and its history, and the system refuses the mistakes that burn firms (signing stale work, filing with open notes, e-filing amounts the client did not sign). The new hire gets a map: areas with status, checks that say what to look at and why, and a trace drawer that answers "where did this come from" in one click.
