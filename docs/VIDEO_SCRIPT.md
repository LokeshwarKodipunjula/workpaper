# Video walkthrough: shot-by-shot script (about 10 minutes)

Lokeshwar Kodipunjula · MiraFlores AI case study · October 2026

Two columns throughout: **SAY** is read word for word, **SHOW** is what is on screen and what the mouse does at that moment. Times are targets; the whole thing runs 9:30 to 10:30 at a normal speaking pace. Cut anything in *[square brackets]* if you are over time.

## Before recording (not in the video)

1. Start the app (`run.bat`, or `docker compose up --build`) and open http://localhost:8000 in a clean browser window at 1440x900 or larger. Close other tabs, hide the bookmarks bar.
2. Pick **Jo Kimura** (firm administrator). Left nav → **Standards, people, time** → scroll to **Demo controls** → click **Reset workpaper**, then **Replay the season**. Wait for the toast.
3. Switch role (top bar) to **Daniel Ortiz** (reviewer). Click **Overview**.
4. Open a second browser window on the right, same URL, as **Priya Raman** (preparer). You will use it once in scene 5 to show live updates. Keep it behind the main window until then.
5. Have `docs/ERRORS_FOUND.md`, `docs/DECISIONS.md` and a terminal in `backend/` open for scene 9.
6. Rehearse the role switches: top bar → role dropdown → name. Each switch is instant.

Recording tip: say the click, then click. Pause half a second after each page loads so the viewer sees it before you talk over it.

---

## Scene 1 · The idea (0:00 – 0:45)

| SAY | SHOW |
|---|---|
| "Hi, I'm Lokeshwar. This is my take on the MiraFlores case study: redesign the tax workpaper from its purpose, not from a spreadsheet." | **Overview** page as Daniel Ortiz. Mouse still. |
| "The purpose of a workpaper is proof. Where did every number come from, what was done to it, who checked it, what is still open. So the unit in this system is not a cell. It is a claim with provenance." | Hover slowly over the four tiles at the top: **Federal · working**, **California · working**, **Open items**, **Sign-offs**. |
| "Two rules shape everything. The packet, the seventy-four documents and three engine runs, is immutable input. And everything the firm does on top of it is an append-only event. The screen you are looking at is a fold over that event log." | Hover the left nav from **Overview** down to **Activity** so the viewer sees the structure. |
| "Let me show you what that buys." | Click nothing yet. |

## Scene 2 · Overview as the reviewer (0:45 – 1:45)

| SAY | SHOW |
|---|---|
| "I'm Daniel, the reviewer, and it's early July. The top bar shows the working federal and California balances, who else is in the file right now, and how many things changed since I last looked." | Point to the top bar: balances, presence avatars, then the **new** chip on **Activity** in the nav. |
| "Return summary versus last year. Anything that moved more than the firm's variance threshold is flagged, and every row is clickable." | Scroll to **Return summary vs last year**. Hover a flagged row. Do not click yet. |
| "Areas. Each area shows its status, how much of it has been verified, failing checks, hours against budget, and who owns it. Status is derived, nobody sets it: a failing check or a blocking note makes an area blocked, open items make it open, then prepared, reviewed, signed." | Scroll to **Areas**. Hover the **Verified** and **Hours / budget** columns. Hover a status dot to show its tooltip. |
| "Below that: open review notes, questions outstanding with the client, and the deadlines, which are the firm's own, including the internal ones." | Scroll through **Open review notes**, **Questions outstanding**, **Deadlines**. Scroll back to the top. |

## Scene 3 · Trace one number (1:45 – 3:30)

| SAY | SHOW |
|---|---|
| "Now the thing everything else hangs on: trace a number. I'll pick the one that cost this client the most." | Left nav → **Investments & digital assets**. The **Lines** tab is selected by default. |
| "Lot N1, a Corvane RSU sale, Form 8949 box B. The engine carried it with a basis of zero." | Scroll the lines table to **F8949.B.N1**. Click the row. The trace drawer opens on the right. |
| "The drawer is the whole story of this value. At the top, the engine value, the effective value, and the rule." | Point to the header of the drawer and the **Engine note**. |
| "Sources, with the exact field on the document and what was printed there. Here: basis, 'not reported', and the pipeline read a blank as zero point zero zero at ninety-eight percent confidence. Blank is not zero." | Scroll to **Sources · exact field on the document**. Hover the basis row with the text "read '' as 0.00". |
| "Where it flows: Schedule D, then adjusted gross income, then California." | Point to the downstream list. |
| "History: the same line across the three engine runs and last year's return." | Scroll to **History · versions and last year**. |
| "Click the source and you're on the page." | Click the basis source link (ev-0498). The document viewer opens on the Corvane 1099-B. |
| "Page text with every extracted value highlighted, a page map with the position boxes, and for each value, which return line it landed on. The page images are simulated in this packet; a real image drops in behind the same boxes and the links stay." | Hover a highlight in the page text, then the page map, then a **landed on** label. Close the viewer. |
| "Back in the drawer: the preparer, Priya, already proposed the fix. Basis nineteen thousand one hundred from the Corvane supplement, which also tells us this vest income is already in W-2 box fourteen. The engine taxed it twice." | Scroll to **Adjustments** in the drawer. Point to the proposed adjustment and read nothing; the reason text is on screen. |
| "The tax effect is over the firm's one-thousand-dollar rule, so it is proposed, not applied. It waits for a partner. That rule is firm data, not code; we'll come back to it." | Point to **Awaiting partner approval**. Close the drawer. |

## Scene 4 · Checks that don't trust the engine (3:30 – 5:00)

| SAY | SHOW |
|---|---|
| "The engine produced this return with confidence. The workpaper's job is to not take its word for it. Every check here re-derives a number from a second place and compares." | Left nav → **Checks**. Filter is **Failing + warnings**, **All areas**. |
| "Three examples. California wage split: W-2 box sixteen covers the whole year, but the family moved to Texas in July. The paystub in the file shows California wages of twenty-two thousand four hundred sixty-nine through the move. No line cited that paystub, so the engine never saw it." | Scroll to **ca_wage_period_split**. Click to expand. Hover the evidence reference D73. |
| "Estimates versus the IRS transcript: the client said 'four thousand, I think'. The transcript says three thousand. The engine used the client." | Scroll to **estimates_vs_irs_transcript**. Expand. |
| "Payoff interest: the Form 1098 says in print that it already includes the interest paid at payoff. The engine added the payoff statement again." | Scroll to **payoff_interest_double_counted**. Expand. |
| "A check can be accepted or waived, but only with a reason recorded under your name, and only by roles the firm allows." | Hover the **Resolve** button on one check. Do not click. |
| "Where did these come from? Documents that were in the file but cited by nothing." | Left nav → **Documents**. Click the filter **Reference only (no line cites it)**. |
| "Paystub, books detail, buyer closing statement, HVAC invoice, Form 1098-C, IRS transcript. Six documents, six of the errors. One column on one page points at all of them." | Hover down the filtered list: D73, D15, D54, D47, D66, D69. Point at the **Landed** and **Where** columns. |

## Scene 5 · Change, people, sign-offs (5:00 – 6:45)

| SAY | SHOW |
|---|---|
| "Changing a number. A small one: Swedish interest was converted at the twenty twenty-four exchange rate. The line's own source says so." | Left nav → **Investments & digital assets** → scroll to **SchB.1.6** → click. In the drawer, **Sources** shows the reference ending in 2024_average. |
| "Priya already corrected it to the twenty twenty-five rate. Under a thousand of tax effect, so it applied immediately, with the tax effect shown and the authority recorded." | Scroll to **Adjustments**. Point to the applied adjustment and its reason. |
| "And the other window, logged in as Priya, updated by itself. That's the WebSocket. Nobody refreshes." | Bring the second window (Priya) alongside for three seconds; the **Activity** chip and the line value match. Push it back. |
| "Everything is on the activity feed, and 'since I last looked' is a real filter, because the log knows when I last read it." | Left nav → **Activity**. Click **Since I last looked**, then **Everything**. |
| "Undo. Nothing is erased: undo appends a compensating event, and a bulk action shares a batch id so one undo reverses all of it." | Hover an **Undo** button and an **Undo batch** button. *[Optional: click Undo on the most recent small adjustment and show the undo entry appear at the top.]* |
| "Now sign-offs. I'll switch to Helen, the partner." | Top bar → role → **Helen Strand**. |
| "The RSU lot adjustment has been waiting for her. Approve." | Left nav → **Investments & digital assets** → click **F8949.B.N1** → in **Adjustments** click **Approve**. The effective value changes and the federal balance in the top bar moves. |
| "Look at the area header. The preparer's sign-off on investments was reopened in March, by the system, when the corrected Meridian 1099 arrived and the engine recomputed sixty-three lines. A sign-off stores a fingerprint of every value in its scope. Change one, and the sign-off reopens with the cause written down." | Close the drawer. Point to the reopened sign-off chip at the top of the area page and hover it for the cause text. |
| "Now the whole return. First I'll leave a blocking note on the business area, the kind a reviewer raises when something must be reconciled before filing." | Left nav → **Business: Lindqvist Studio** → **Area note / judgment** → tick blocking → type "Reconcile 1099-K before filing" → save. |
| "Filing page. Try the partner sign-off on the whole return." | Left nav → **Filing & after** → click **Partner sign-off on the whole return**. Refused. Read the toast: "1 open review note(s) block the return." |
| "Refused, with the reason. Resolve the note and try again." | Back to **Business: Lindqvist Studio** → tab **Open notes** → **Resolve**. Back to **Filing & after** → **Partner sign-off on the whole return**. Refused again: "7 adjustment(s) await partner approval." |
| "Still refused: seven corrections over the firm's threshold are waiting for me, listed right here with their tax effect. Nothing a partner has not seen gets signed. Approve them." | Point to **Awaiting partner approval · 7**. Click **Approve** on each row; the list empties and the top-bar balance moves with each one. *[Speed this up in the edit if needed.]* |
| "Now it signs." | Click **Partner sign-off on the whole return**. The chip **partner ✓** appears under the actions. |

## Scene 6 · Roles and protection (6:45 – 7:30)

| SAY | SHOW |
|---|---|
| "Permissions are checked by the server on every write, and served to the UI with the actor list, so the screen has no copy of the rules to drift. Marcus is a preparer without sensitive-data clearance." | Top bar → role → **Marcus Bell**. |
| "Household: Social Security numbers masked. The same for bank and account numbers and the IP PIN, anywhere in any response, because masking is one function on the way out of the API, not something each page remembers to do." | Left nav → **Household & people**. Point to the masked SSNs. Then **Documents** → open D71 (Theo's Social Security card) → masked there too. |
| "Jo, the administrator, sees who looked at unmasked data and when." | Top bar → **Jo Kimura** → **Standards, people, time** → scroll to **Sensitive-data view log**. Point to Helen's view of D71 and Daniel's household view. |
| "The standards are data. Variance threshold, verification types, rules the server enforces, required steps. Change the variance threshold and the flagged swings on the overview change with it. The partner-approval threshold in that rule text is what the server reads." | Scroll up to **Standards**. Type a new percent in **Flag a line when it moves more than**, click **Set %**. Hover the rule "Any adjustment with a tax effect over 1,000 requires partner sign-off". |
| "People, assignments and time against budget, by area." | Scroll through **People & roles**, **Assignments & deadlines**, **Time against budget**. |

## Scene 7 · Client and filing (7:30 – 9:00)

| SAY | SHOW |
|---|---|
| "Filing. The return is signed, so as the partner I can send it to the client." | Top bar → **Helen Strand** → **Filing & after** → **Send to client for approval**. The stepper moves to **With client**. |
| "Now I'm Ngozi, the client. A plain-language summary, the questions she answered, which became evidence on the lines, and a signature with her five-digit PIN." | Top bar → **Ngozi Okafor**. On **Your return**: hover **Federal**, **California**, the answered questions. Type `12345` in **Your 5-digit PIN**, click **I approve and sign**. |
| "Her approval stores a fingerprint of the amounts she saw. Watch what happens if the return changes after she signed. Daniel, the reviewer, touches one small line." | Top bar → **Daniel Ortiz** → **Investments & digital assets** → click **SchB.1.6** → **Adjust** → new value 1870, reason "Rounding per statement" → save. |
| "Back as Helen, on Filing: the client's approval is void, automatically, with the cause in the history. My own whole-return sign-off has reopened for the same reason. And e-file is refused. This is exactly what went wrong in the real timeline: the client signed on v3 while three new facts were already in hand." | Top bar → **Helen Strand** → **Filing & after**. Point to the history line "Client approval voided: SchB.1.6 changed...", then the **partner reopened** chip. Click **Transmit e-file** → refused, reason in the toast. |
| "Re-sign, re-send, she re-signs, e-file." | **Partner sign-off on the whole return** → **Send to client for approval** → switch to **Ngozi** → PIN → **I approve and sign** → switch to **Helen** → **Transmit e-file**. Stepper: **E-filed**. |
| "The IRS rejected the real return: dependent name and TIN mismatch. Record it." | Click **Record rejection**. The detail defaults to R0000-504-02. |
| "The workpaper flagged Theo's SSN on day one. The organizer has two digits transposed; the 2024 return and his card both disagree. Two checks, before anyone filed." | Left nav → **Checks** → find **ssn_prior_year:theo** and **ssn_mismatch:ev-1080** (use the status filters if needed). Expand one. |
| "Record acceptance and the filed return is frozen. Open an amendment, and new adjustments go on the amendment layer, on top of the frozen record, never into it." | Back to **Filing & after** → **Record acceptance (freeze)** → point to "The filed return is frozen." → **Open amendment**. |
| "Two years later the examination letter arrives. The notice response is a record generated from the frozen return: each item answered from the lines and the evidence that was attached at the time." | Scroll to **Notices** → click **Open the self-contained response record**. Scroll through the two items and their evidence. |

## Scene 8 · Records (9:00 – 9:30)

| SAY | SHOW |
|---|---|
| "Every record a CPA expects is a view over the graph and the log. Nothing is stored twice." | Left nav → **Records**. Hover the list of record titles. |
| "Depreciation by asset, federal, California and AMT side by side. Sales detail: three hundred two lots collapsed to totals by box and broker, exceptions first, which is how the RSU lots and the missing lot M18 surface. State split. Carryovers, and the carry-forward plan with the one-hundred-ten percent safe harbor." | Click **Depreciation by asset** (3 s), **Sales detail (Form 8949)** (5 s, point to the exceptions block), **State split (California)** (3 s), **Carry forward and 2026 plan** (3 s). |

## Scene 9 · Decisions and trade-offs (9:30 – 10:30)

| SAY | SHOW |
|---|---|
| "Technical decisions, briefly. FastAPI and Pydantic, SQLAlchemy over PostgreSQL with SQLite for local, WebSockets for presence and live updates, React with Vite, Docker. Twenty-eight pytest tests pin the rules: fingerprints, permissions, filing transitions, masking, undo." | Switch to the editor. Show the `backend/app/` file list, then the terminal with `pytest -q` output ending in `28 passed`. *[Run it before recording so it is already on screen.]* |
| "Why event sourcing: undo, 'since I last looked', the frozen filing, the notice response and next year's roll-forward are all the same mechanism. The trade-off is that state is rebuilt per request. At one return that is a few hundred events and faster than a database round trip. For a firm I would snapshot." | Show `backend/app/events.py` for two seconds. |
| "Why the packet stays in memory: it is immutable and small, and replacing it is replacing a file. Search is linear; for many clients it moves to Postgres full-text." | Show `backend/app/packet.py` briefly. |
| "Why no language model in the product: a CPA and an examiner need a trail that reproduces. Every check is deterministic. A model would plug in for drafting client questions, narrating swings, and reading real page images." | Back to the browser, **Checks** page. |
| "Tax effects use the engine's own per-dollar rates. The real system recomputes, and the what-if page shows both the estimate and the engine's priced alternatives." | Left nav → **What-if**. Hover **Alternatives the engine has already priced**. |
| "How I used AI. I decided the design, the stack and the module boundaries first, then used Claude Code as the implementer, module by module, reviewing between steps. For the planted mistakes I ran one analysis pass per area with the instructions I'd give a staff accountant, then re-derived every candidate myself from the raw data before it became a check. Twenty-five confirmed errors are in ERRORS_FOUND; the decision log is in DECISIONS." | Show the `docs/ERRORS_FOUND.md` table for three seconds, then `docs/DECISIONS.md`. |
| "Next: snapshotting, a PDF client copy, email notifications, real page images, and versioned standards per firm. Thanks for watching." | Back to the browser, **Overview**. Hold two seconds. Stop recording. |

---

## Quick reference while recording

**Role switches in order:** Daniel Ortiz → Helen Strand → Marcus Bell → Jo Kimura → Helen Strand → Ngozi Okafor → Daniel Ortiz → Helen Strand → Ngozi Okafor → Helen Strand.

**Line keys you click:** `F8949.B.N1` (RSU lot), `SchB.1.6` (Swedish interest, twice: once to show it, once for Daniel's small change in scene 7).

**Why the whole-return sign-off can refuse you, in the order the server checks:** an open blocking note anywhere; then any adjustment still awaiting partner approval; then the rule that you may not sign work you prepared yourself. That last one is why Daniel, not Helen, makes the small change in scene 7.

**Checks you expand:** `ca_wage_period_split`, `estimates_vs_irs_transcript`, `payoff_interest_double_counted`, `ssn_prior_year:theo`.

**Documents you name:** D73 paystub, D15 books detail, D54 buyer closing statement, D47 HVAC invoice, D66 Form 1098-C, D69 IRS transcript, D71 Theo's SSN card, D31 Meridian corrected 1099.

**Numbers you say:** basis 19,100 · W-2 box 14 · CA wages 22,469 through the move · 4,000 said vs 3,000 on the transcript · 63 lines changed by the corrected 1099 · 302 lots · 28 tests · 25 errors.

**If something refuses unexpectedly:** read the toast aloud. The refusals are the product; a reason in the toast is a feature, not a bug.

**If you are over time:** drop the second window in scene 5, the undo click, the variance-threshold edit in scene 6, and the Records clicks beyond Sales detail. That saves about 90 seconds.
