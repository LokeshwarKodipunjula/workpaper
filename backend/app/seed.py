"""Replay the season: seed the event log with the actions the firm would have taken.

Every event is stamped with the packet's own timeline dates, so "since I last
looked", version compare and the sign-off reopen behaviour all have history to
show. The findings seeded as adjustments are the planted mistakes documented in
docs/ERRORS_FOUND.md; each carries its evidence refs.
"""
from __future__ import annotations

from .events import EventStore
from .packet import Packet
from .service import Service, tax_effect


def seed_events(p: Packet, store: EventStore, svc: Service) -> int:
    store.reset()
    n = 0

    def add(type, actor, role, payload, target=None, area=None, at=None, batch_id=None):
        nonlocal n
        n += 1
        return store.append(type, actor, role, payload, target=target, area=area, batch_id=batch_id, at=at)

    def adjust(actor, role, key, new_value, reason, authority, evidence, at, category=None, status=None):
        l = p.line(key)
        te = tax_effect(p, key, l["value"], new_value, category=category)
        requires = (abs(te["federal"]) > 1000 or abs(te["california"]) > 1000) and role != "partner"
        return add("adjustment.proposed", actor, role, {"old_value": l["value"], "new_value": new_value, "reason": reason, "authority": authority, "category": te["category"],
                                                          "tax_effect": te, "requires_partner": requires, "status": status or ("proposed" if requires else "applied"),
                                                          "evidence": evidence, "layer": None, "engine_value": l["value"]}, target=key, area=p.area_of_line(key), at=at)

    def verify(actor, role, target, vtype, note, at, batch=None):
        area = p.area_of_line(target) if p.line(target) else (p.area_of_document(p.ev_by_id[target]["document_id"]) if target in p.ev_by_id else p.area_of_document(target))
        return add("verification.recorded", actor, role, {"type": vtype, "note": note}, target=target, area=area, at=at, batch_id=batch)

    def note(actor, role, target, text, kind="review", at=None, blocking=False, assigned_to=None, authority=None, area=None, due=None, alternatives=None, step=None):
        a = area or (p.area_of_line(target) if target and p.line(target) else (p.area_of_document(target) if target in p.doc_by_id else "return_summary"))
        return add("note.created", actor, role, {"text": text, "kind": kind, "blocking": blocking, "severity": "normal", "assigned_to": assigned_to, "due": due, "authority": authority, "alternatives": alternatives, "step": step}, target=target, area=a, at=at)

    # ---- March: work starts (tl-05), assignments, transcript pulled (tl-06)
    for area, who in [("wages_and_stock_compensation", "st-01"), ("investments_and_digital_assets", "st-01"), ("business", "st-01"), ("rentals_and_sale", "st-01"), ("pass_throughs_and_basis", "st-01"), ("retirement_and_hsa", "st-01"), ("deductions_and_credits", "st-04"), ("payments_and_penalties", "st-01"), ("california", "st-02"), ("intake_and_engagement", "st-01")]:
        add("assignment.set", "st-05", "firm_administrator", {"area": area, "assignee": who, "due": "2026-03-27"}, target=area, area=area, at="2026-03-09T15:05:00Z")
    add("time.logged", "st-01", "preparer", {"area": "intake_and_engagement", "hours": 1.0, "note": "Engagement, identity, prior return read"}, target="intake_and_engagement", area="intake_and_engagement", at="2026-03-09T18:00:00Z")
    for step in ["Engagement letter and consents signed", "Prior-year return reviewed"]:
        s = note("st-01", "preparer", None, f"Required step: {step}", kind="required_step", at="2026-03-09T18:10:00Z", area="intake_and_engagement", step=step)
        add("note.resolved", "st-01", "preparer", {"note_id": s.id, "resolution": "Done; D01, D02, D06 on file."}, target=None, area="intake_and_engagement", at="2026-03-09T18:11:00Z")
    verify("st-01", "preparer", "D06", "agreed_to_prior_year", "2024 return as filed matches prior_years.return_2024 lines (sample of 20).", "2026-03-09T19:00:00Z")
    note("st-01", "preparer", None, "Prior preparer open item: Form 3520 for the 2023 Swedish inheritance (over 100,000) - no record it was filed. Outside our 2025 engagement; raise with client and partner.", kind="memo", at="2026-03-09T19:20:00Z", area="intake_and_engagement", assigned_to="st-03")

    # Wages: agree W-2s, D10 is a duplicate image
    b = "batch_seed_w2"
    for k in ["F1040.1a", "F1040.25a", "SchCA540NR.1.A"]:
        verify("st-01", "preparer", k, "agreed_to_source_document", "Agreed to D08 and D09 box by box; D10 is a phone photo of D09 and is counted once.", "2026-03-10T16:00:00Z", batch=b)
    add("time.logged", "st-01", "preparer", {"area": "wages_and_stock_compensation", "hours": 2.5}, target="wages_and_stock_compensation", area="wages_and_stock_compensation", at="2026-03-10T22:00:00Z")

    # Investments: the client said no sales; ask
    q1 = add("question.asked", "st-01", "preparer", {"to": "client", "text": "Your organizer says no investments were sold in 2025, but Northlake, Meridian and Brightpath report 282 sales and Coinhaven 12 dispositions. Please confirm these are all your accounts and that there are no others (including any closed during the year).", "due": "2026-03-20"}, target="SchD.16", area="investments_and_digital_assets", at="2026-03-11T15:00:00Z")
    add("question.answered", "cu-01", "client", {"question_id": q1.id, "answer": "Yes - those are all of them. Brightpath is the direct-indexing account; I didn't think of it as 'selling'. No other accounts."}, target="SchD.16", area="investments_and_digital_assets", at="2026-03-12T02:10:00Z")
    add("check.override", "st-02", "reviewer", {"check_id": "qa_sales_conflict", "status": "accepted", "reason": "Client confirmed all accounts (see answered question on SchD.16)."}, target="qa_sales_conflict", at="2026-03-12T16:00:00Z")
    add("check.override", "st-02", "reviewer", {"check_id": "diag:QUESTIONNAIRE_SALES_CONFLICT", "status": "accepted", "reason": "Same as above."}, target="diag:QUESTIONNAIRE_SALES_CONFLICT", at="2026-03-12T16:01:00Z")

    # Transcript pulled (tl-06): estimated payments
    verify("st-01", "preparer", "F1040.26", "agreed_to_third_party_record", "IRS account transcript D69 (as of 2026-03-12) shows the 670 payments; see payments_and_penalties checks for the Q4 question.", "2026-03-12T17:00:00Z")

    # Business area: a blocking reviewer note and a judgment call
    n1 = note("st-02", "reviewer", "SchC.1", "Gross receipts must be reconciled to the five 1099-NECs (142,000) and the 1099-K (12,400) before I sign. Show the books-to-tax bridge.", at="2026-03-13T15:00:00Z", blocking=True, assigned_to="st-01", due="2026-03-20")
    add("note.replied", "st-01", "preparer", {"note_id": n1.id, "text": "Bridge is in Records > Books to tax: books 168,850 = 1099-NEC 142,000 + 1099-K 12,400 + checks/other 14,450 (qa-24)."}, target="SchC.1", area="business", at="2026-03-16T20:00:00Z")
    add("note.resolved", "st-02", "reviewer", {"note_id": n1.id, "resolution": "Bridge agreed. Resolved."}, target="SchC.1", area="business", at="2026-03-17T15:00:00Z")
    note("st-01", "preparer", "SchC.13", "Studio equipment (38,000, D22): take 100% special depreciation rather than section 179. Same 2025 federal result; section 179 would add back for California (CA limit 25,000) - see what-if 'equipment_section179'.", kind="election", at="2026-03-16T21:00:00Z", authority="IRC 168(k); R&TC 17255; engine what_if.equipment_section179", alternatives="Section 179 election; MACRS without bonus")
    add("time.logged", "st-01", "preparer", {"area": "business", "hours": 3.0}, target="business", area="business", at="2026-03-16T22:00:00Z")

    # Preparer sign-off on wages, then the corrected Meridian 1099 (tl-07) reopens investments work
    add("signoff.given", "st-01", "preparer", {"scope": "wages_and_stock_compensation", "level": "preparer", "fingerprint": "seed-v2-wages"}, target="wages_and_stock_compensation", area="wages_and_stock_compensation", at="2026-03-17T22:00:00Z")
    so = add("signoff.given", "st-01", "preparer", {"scope": "investments_and_digital_assets", "level": "preparer", "fingerprint": "seed-v1-invest"}, target="investments_and_digital_assets", area="investments_and_digital_assets", at="2026-03-17T22:05:00Z")
    add("signoff.reopened", "system", "system", {"signoff_id": so.id, "cause": "Corrected Meridian 1099 (D31) received 2026-03-18; engine recomputed v2 with 63 line changes.", "cause_event_id": "timeline:tl-07"}, target="investments_and_digital_assets", area="investments_and_digital_assets", at="2026-03-19T07:41:00Z")
    note("st-01", "preparer", "D31", "Corrected 1099 changed 63 lines (see Versions: v1 -> v2). Page 32 'Additional transactions' still unread by the pipeline: the 250 summary-vs-lots gap is on that page.", at="2026-03-19T16:00:00Z", assigned_to="st-01")

    # Marcus joins (tl-09) and works deductions without clearance; a masked view
    add("view.sensitive", "st-02", "reviewer", {"field": "household", "subject": "household"}, target="household", area="intake_and_engagement", at="2026-03-24T16:00:00Z")
    add("time.logged", "st-04", "preparer", {"area": "deductions_and_credits", "hours": 1.5}, target="deductions_and_credits", area="deductions_and_credits", at="2026-03-25T22:00:00Z")

    # Client call (tl-10) becomes evidence on Schedule C lines
    for k, txt in [("SchC.25", "Call 2026-03-26: home internet 50% business, mobile plan 70% business (call-01)."), ("SchC.24b", "Call 2026-03-26: meals are client meetings and contractor lunches, no entertainment (call-01).")]:
        verify("st-01", "preparer", k, "confirmed_with_client", txt, "2026-03-26T18:00:00Z")

    # Extension (tl-13)
    add("filing.status", "st-02", "reviewer", {"status": "extension_filed", "detail": "Form 4868 with 36,000 and FTB 3519 with 0, estimated from v2 (what_if.extension). Ridgeline K-1 still outstanding.", "fingerprint": "seed-v2"}, target="filing", at="2026-04-14T15:00:00Z")
    add("time.logged", "st-02", "reviewer", {"area": "partner_review", "hours": 0.5, "note": "Extension estimate"}, target="partner_review", area="partner_review", at="2026-04-14T15:30:00Z")

    # June: late documents, v3, crypto basis question (msg-07), St. Brigid (msg-08)
    q2 = add("question.asked", "st-01", "preparer", {"to": "client", "text": "Coinhaven lot C6 (BTC) has no cost basis on the 1099-DA because it was transferred in. Where and when was it bought, and for how much? Any statement or export from the original exchange?", "due": "2026-07-01"}, target="F8949.H.C6", area="investments_and_digital_assets", at="2026-06-24T15:00:00Z")
    add("question.answered", "cu-02", "client", {"question_id": q2.id, "answer": "Bought on another exchange in March 2021 for about 3,050 and moved to Coinhaven in June 2021. That exchange shut down; I only have an email confirmation of the deposit (will upload)."}, target="F8949.H.C6", area="investments_and_digital_assets", at="2026-06-30T18:02:00Z")
    q3 = add("question.asked", "st-04", "preparer", {"to": "client", "text": "The handwritten St. Brigid receipt is hard to read (the pipeline read 1,500 at 0.41 confidence). Can you confirm the amount from your bank statement?", "due": "2026-07-03"}, target="SchA.11", area="deductions_and_credits", at="2026-06-25T16:00:00Z")
    add("question.answered", "cu-01", "client", {"question_id": q3.id, "answer": "St. Brigid confirmed by phone the gift was 1,500 - matches our bank statement (check #2207, 12/21/2025)."}, target="SchA.11", area="deductions_and_credits", at="2026-07-01T16:40:00Z")

    # Judgment calls and due diligence
    note("st-02", "reviewer", "F8949.H.C6", "Crypto lot C6 basis: client's statement (3,050, March 2021) is uncorroborated after the exchange closed. Position: use 3,050 with the deposit email as support; holding period long-term from the original purchase. Disclose if the email cannot be produced.", kind="judgment", at="2026-07-02T15:00:00Z", authority="IRC 1012; Rev. Proc. 2024-28 (unit-by-unit basis); IRS FAQ on digital assets Q38-Q40", alternatives="Zero basis (engine); client estimate without support")
    note("st-01", "preparer", "F8812.1", "Form 8867 due diligence: Theo (8) qualifies for the child tax credit; Ada (19, full-time student, lived with the family 12 months, support test met, her own 4,100 W-2) qualifies for the credit for other dependents only. Knowledge requirement met via organizer, 1098-T and SSN cards.", kind="due_diligence", at="2026-07-02T16:00:00Z", authority="IRC 6695(g); Form 8867 instructions", step="Due diligence completed")
    note("st-02", "reviewer", "F2210.19", "Underpayment penalty 164: computed on v3 payments. Do not request first-time abatement in the return; the client paid late and the FTP penalty after 4/15 is separate. Advise the client in the cover letter.", kind="penalty", at="2026-07-02T16:30:00Z", authority="IRC 6654; Form 2210 instructions")
    note("st-01", "preparer", "F8938.1.max", "FBAR (FinCEN 114) is outside the engagement; client confirmed they file it themselves (prior preparer note). Reminder sent with the 10/15 automatic extension date.", kind="memo", at="2026-07-02T17:00:00Z")

    # Sensitive-data rule in action
    add("view.sensitive", "st-03", "partner", {"field": "document", "subject": "D71"}, target="D71", area="intake_and_engagement", at="2026-07-13T19:30:00Z")

    # Carry-forward notes for next year
    add("carryforward.noted", "st-01", "preparer", {"item": "minimum_tax_credit_from_2025_amt", "value": 3871, "note": "Form 8801 in 2026 - ISO deferral item."}, target="minimum_tax_credit_from_2025_amt", at="2026-07-03T15:00:00Z")
    add("carryforward.noted", "st-01", "preparer", {"item": "ca_depreciation_basis_differences", "value": "see carryovers_out.california", "note": "Studio equipment: federal 100% bonus vs California MACRS - track the CA basis for each asset."}, target="ca_depreciation_basis_differences", at="2026-07-03T15:05:00Z")

    # verification of the low-confidence read, now confirmed
    verify("st-04", "preparer", "ev-1049", "confirmed_with_client", "msg-08: parish confirmed 1,500; bank check #2207 12/21/2025.", "2026-07-01T17:00:00Z")

    # ---- Corrections of the engine's confident mistakes (see docs/ERRORS_FOUND.md). Big ones wait for the partner.
    adjust("st-01", "preparer", "F8949.B.N1", 140, "RSU lot RSU-2502: broker basis 'not reported'; Corvane supplement gives adjusted basis 19,100 (400 sh at 47.75 vest FMV, already in W-2 box 14). Gain 140.", "Supplement D11; IRC 83; Form 8949 code B", ["ev-0066", "ev-0067", "ev-0498", "D11"], "2026-07-02T18:00:00Z")
    adjust("st-01", "preparer", "F8949.B.N3", -620, "RSU lot RSU-2505: supplement basis 19,100; loss 620.", "Supplement D11; Form 8949 code B", ["ev-0068", "ev-0069", "ev-0516"], "2026-07-02T18:02:00Z")
    adjust("st-01", "preparer", "F8949.E.N4", 5880, "RSU lot RSU-2308: supplement basis 9,420; long-term gain 5,880.", "Supplement D11; Form 8949 code B", ["ev-0070", "ev-0071", "ev-0525"], "2026-07-02T18:04:00Z")
    adjust("st-01", "preparer", "SchB.1.2", 0, "Northlake Bank 1099-INT (D29) is the same sweep-program interest already in the consolidated 1099 (D28, account 7731). Counted once.", "D28 page 1; D29", ["ev-0492", "ev-0538", "D29"], "2026-07-02T18:10:00Z")
    adjust("st-01", "preparer", "SchB.1.6", 1871, "Sparbanken interest SEK 18,450 converted at the 2025 average rate 9.86 (engine used the 2024 rate 10.56).", "Treasury/engine fx 2025_average", ["ev-0960", "ref:fx.SEK.2025_average"], "2026-07-02T18:12:00Z")
    adjust("st-01", "preparer", "SchC.1", 151300, "Gross receipts: the 12,400 Form 1099-K is inside Atlas Outdoor Gear's 41,200 already in books revenue (D15 page 3). Books total income 151,300 reconciles to the 1099-NECs, the 1099-K and 9,300 of small-client deposits.", "Books D14/D15; Forms 1099-NEC/K", ["ev-0103", "ev-0127", "doc:D15#page3"], "2026-07-02T18:20:00Z")
    adjust("st-01", "preparer", "SchC.44a", 8100, "Mileage log page 3 is a second scan of the May-Aug page (page 2); its 3,700 miles were summed twice.", "D23 page 3 (duplicate scan)", ["doc:D23#page3", "ev-0315", "ev-0477"], "2026-07-02T18:25:00Z")
    adjust("st-01", "preparer", "SchC.25", 2172, "Telephone 70% business (1,512) and internet 50% (660) per client call; books carry 100%.", "call-01; IRC 262", ["call-01", "ev-0101", "ev-0095"], "2026-07-02T18:30:00Z")
    adjust("st-01", "preparer", "Sch1.17", 0, "Self-employed health insurance not allowed: Erik was eligible for Ngozi's subsidized employer plan all year (qa-25). Premiums go to Schedule A medical (below the floor).", "IRC 162(l)(2)(B); qa-25; prior preparer 2024 note", ["qa-25", "ev-0484", "D25"], "2026-07-02T18:35:00Z")
    adjust("st-04", "preparer", "F8283.A1.vehicle", 2900, "Donated 2012 Subaru: charity sold it at auction; deduction limited to Form 1098-C box 4c gross proceeds 2,900, not the client's KBB 6,000.", "IRC 170(f)(12); Form 1098-C D66", ["ev-1054", "D66", "qa-39", "call-01"], "2026-07-02T19:00:00Z")
    adjust("st-04", "preparer", "SchA.8a", 19697, "Lonestar payoff interest 2,150 is already inside the Form 1098 box 1 (D55 says so); removed the double count.", "D55 box 1; D56", ["ev-1029", "ev-1032", "D55", "D56"], "2026-07-02T19:05:00Z")
    adjust("st-04", "preparer", "SchA.5b", 6508, "Travis County tax 13,420 paid from escrow less the seller's 6,912 credit at closing for 01/01-07/07/2025 (D54).", "IRC 164(d); buyer closing statement D54", ["ev-1027", "ev-1036", "D54"], "2026-07-02T19:10:00Z")
    adjust("st-01", "preparer", "F1040.26", 12000, "4th-quarter federal estimate is 3,000 per the IRS transcript (2026-01-15), not the client's '4,000 I think'.", "IRS account transcript D69", ["agency:/irs_account_transcript_2025/0", "qa-41", "D67"], "2026-07-02T19:20:00Z")
    adjust("st-01", "preparer", "F540NR.72", 10500, "The 2025-09-15 Web Pay of 3,500 was designated tax year 2024 (D68) and FTB holds it as a 2024 credit; 2025 estimates are 10,500.", "FTB account record; D68", ["ev-1076", "ev-1075", "agency:/ftb_account"], "2026-07-02T19:25:00Z")
    adjust("st-01", "preparer", "SchCA540NR.1.E", 129569, "California-source wages: Corvane 107,100 (all CA) + Halvorsen 22,469 through the 07/15/2025 move per the paystub (D73). Box 16 covers the whole year in error; W-2c requested.", "R&TC 17041/17951; FTB Pub 1031; D73", ["ev-1081", "ev-0047", "D73", "qa-45"], "2026-07-02T19:40:00Z")
    adjust("st-01", "preparer", "F8949.H.C6", 2275, "Coinhaven lot C6: basis 3,050 (bought March 2021, moved to Coinhaven June 2021 per client); gain 2,275 and long-term.", "msg-07; IRC 1012; reviewer judgment note", ["msg-07", "ev-0879", "ev-0881"], "2026-07-02T19:50:00Z")
    note("st-01", "preparer", "SchE.14A", "HVAC: full system replacement (new heat pump, air handler, line set, permit) is a restoration of a building system - capitalize 11,000 as a 27.5-year improvement placed in service 2025-08-12 instead of expensing in repairs. Engine what-if prices the change at +3,633 federal.", kind="judgment", at="2026-07-02T20:00:00Z", authority="Reg. 1.263(a)-3(k)(1)(vi); call-01; D47", alternatives="Expense as repair (engine); de minimis (not available at 11,000)")
    adjust("st-01", "preparer", "SchE.14A", 2300, "Repairs 13,300 less the 11,000 HVAC replacement, which is capitalized (see judgment note).", "Reg. 1.263(a)-3(k); D47", ["ev-1000", "ev-1004", "D47"], "2026-07-02T20:05:00Z")
    adjust("st-01", "preparer", "F8949.B.total", 37660, "Lot M18 Ironwood REIT (cash in lieu, proceeds 250, basis 310, short-term loss 60) is on Meridian page 32, which the pipeline never read. Added from the page.", "D31 page 32", ["doc:D31#page32", "ev-0703"], "2026-07-02T20:08:00Z")
    verify("st-01", "preparer", "ev-1045", "agreed_to_source_document", "Provider EIN printed 74-3829156; pipeline transposed digits. Corrected on Form 2441.", "2026-07-02T20:10:00Z")
    add("time.logged", "st-01", "preparer", {"area": "california", "hours": 1.5}, target="california", area="california", at="2026-07-02T21:00:00Z")
    add("time.logged", "st-01", "preparer", {"area": "deductions_and_credits", "hours": 1.0}, target="deductions_and_credits", area="deductions_and_credits", at="2026-07-02T21:05:00Z")

    add("read.marker", "st-02", "reviewer", {}, at="2026-07-01T12:00:00Z")
    return n
