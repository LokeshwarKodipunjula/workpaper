"""Targeted checks: the traps a reviewer must catch in this packet.

Each one re-derives a figure from documents, client statements, prior years or
agency records and compares it with the engine. They are written as general
rules (supplement-lot matching, state-wage period split, duplicate payer
matching, closing-statement proration ...) applied to this household's data, so
they would fire on the next client too.
"""
from __future__ import annotations

import re
from datetime import date

from .checks import check, mk, _num
from .events import State
from .packet import Packet


def _ev(p: Packet, doc: str, field: str):
    return next((e for e in p.evs_by_doc.get(doc, []) if e["field"] == field), None)


def _lot_basis_from_label(label: str) -> float | None:
    m = re.search(r"basis ([\d,\.]+)", label)
    return float(m.group(1).replace(",", "")) if m else None


@check
def t_supplement_lot_match(p: Packet, s: State, vid: str):
    """1099-B lots with blank/zero basis that a stock-plan supplement prices."""
    out = []
    supp = [e for e in p.extracted_values if e["document_id"] == "D11" and e["field"].endswith("_adjusted_basis")]
    supp_by_date = {}
    for e in supp:
        d = _ev(p, "D11", e["field"].replace("_adjusted_basis", "_acquired"))
        if d:
            supp_by_date[str(d["value"])] = (e, _num(e["value"]))
    for k, l in p.lines(vid).items():
        if not k.startswith("F8949.") or "Corvane" not in l["label"]:
            continue
        basis = _lot_basis_from_label(l["label"])
        m = re.search(r"acquired ([\d-]+)", l["label"])
        acq = m.group(1) if m else None
        if basis == 0 and acq in supp_by_date:
            e, b = supp_by_date[acq]
            eff, adj = s.effective_value(k, l["value"])
            fixed = adj is not None
            out.append(mk(f"supplement_lot:{k}", "wages_and_stock_compensation", f"RSU lot {k} carried at zero basis; the Corvane supplement prices it at {b:,.0f}",
                          "pass" if fixed else "fail",
                          f"Broker reported basis 'not reported' and the engine used 0.00, so the {b:,.0f} of vest income already in W-2 box 1 (box 14 RSU 38,200) is taxed twice. Supplement {e['id']} gives adjusted basis {b:,.0f} for the lot acquired {acq}. Gain should be {float(l['value']) - b:,.0f}, not {float(l['value']):,.0f}.",
                          [k, e["id"], "D11", *l["sources"], "ev-0027"], {"supplement": e, "basis": b}, "Adjust the lot to proceeds minus the supplement basis (code B) and let the partner approve."))
    return out


@check
def t_ca_wage_period_split(p: Packet, s: State, vid: str):
    """Part-year resident: W-2 box 16 equal to full wages when employment spans the move date."""
    out = []
    move = next((r["from"] for r in p.household["residency"] if r["state"] != "CA"), None)
    if not move:
        return out
    stub = _ev(p, "D73", "ytd_ca_wages")
    l = p.line("SchCA540NR.1.E", vid)
    if not l:
        return out
    box16_h = _ev(p, "D09", "box16")
    box1_h = _ev(p, "D09", "box1")
    boxW_h = _ev(p, "D09", "box12_W")
    full_year = box16_h and box1_h and abs(float(box16_h["value"]) - float(box1_h["value"]) - float(boxW_h["value"] if boxW_h else 0)) < 1
    eff, adj = s.effective_value("SchCA540NR.1.E", l["value"])
    corvane_ca = float(_ev(p, "D08", "box16")["value"])
    expected = corvane_ca + (float(stub["value"]) if stub else 0)
    if full_year and abs(float(eff) - float(l["value"])) < 1:
        out.append(mk("ca_wage_period_split", "california", "California-source wages taken as 100% of Halvorsen wages although the client moved to Texas on " + move, "fail",
                      f"Halvorsen W-2 box 16 ({float(box16_h['value']):,.0f}) equals box 1 plus the HSA code W, i.e. the whole June-December period, but the paystub D73 (in file, cited by no line) shows California taxable wages of {float(stub['value']) if stub else 0:,.0f} through 07/15/2025 and a work-location change to Austin. Column E should be about {expected:,.0f} (Corvane {corvane_ca:,.0f} + Halvorsen CA period), not {float(l['value']):,.0f}.",
                      ["SchCA540NR.1.E", "ev-0047", "ev-1081", "D73", "D09", "qa-45", "qa-03"], {"expected": expected}, "Adjust SchCA540NR.1.E to the CA-period wages; request a W-2c from Halvorsen; the 4,180 CA withholding stays creditable."))
    elif adj:
        out.append(mk("ca_wage_period_split", "california", "California-source wages split at the move date", "pass", f"Adjusted to {float(eff):,.0f}.", ["SchCA540NR.1.E"]))
    return out


@check
def t_1099k_double_count(p: Packet, s: State, vid: str):
    l = p.line("SchC.1", vid)
    books = _ev(p, "D14", "total_income")
    k = _ev(p, "D21", "box1a")
    if not (l and books and k):
        return []
    eff, adj = s.effective_value("SchC.1", l["value"])
    engine_added = abs(float(l["value"]) - float(books["value"]) - float(k["value"])) < 1
    detail = p.page("D15", 3)
    in_books = detail and "12,400.00 arrived through Paywell" in detail["printed_content"]
    if engine_added and in_books and adj is None:
        return [mk("schc_1099k_in_books", "business", "Schedule C gross receipts add the 1099-K 12,400 that is already inside the books", "fail",
                   f"Engine: books total income {float(books['value']):,.0f} + Form 1099-K {float(k['value']):,.0f} = {float(l['value']):,.0f}. The books transaction detail (D15 page 3, cited by no line) says the 12,400 of Paywell card receipts is part of Atlas Outdoor Gear's 41,200 already recorded in Sales. Gross receipts should be {float(books['value']):,.0f}.",
                   ["SchC.1", "ev-0103", "ev-0127", "doc:D15#page3", "D21"], None, "Adjust SchC.1 to the books figure; keep the 1099-K reconciliation (142,000 NEC + 12,400 K inside 151,300) in the books-to-tax record for the examiner.")]
    if adj:
        return [mk("schc_1099k_in_books", "business", "Schedule C gross receipts reconciled to the books and third-party forms", "pass", f"Adjusted to {float(eff):,.0f}.", ["SchC.1"])]
    return []


@check
def t_duplicate_pages_and_documents(p: Packet, s: State, vid: str):
    out = []
    # duplicate scanned page inside a document whose page totals are summed
    d = p.doc_by_id.get("D23")
    if d:
        texts = [pg["printed_content"] for pg in d["pages"]]
        for i, t in enumerate(texts):
            if "Second scan" in t or "second scan" in t:
                l = p.line("SchC.44a", vid)
                eff, adj = s.effective_value("SchC.44a", l["value"]) if l else (None, None)
                page_total = next((e for e in p.evs_by_doc["D23"] if e["page"] == i + 1 and "total" in e["field"]), None)
                out.append(mk("mileage_duplicate_page", "business", "Mileage log page 3 is a second scan of page 2; its total was summed again", "pass" if adj else "fail",
                              f"The scan says so itself. The engine's rule sums the four page totals, so {float(page_total['value']) if page_total else 0:,.0f} business miles are counted twice. Business miles should be {float(l['value']) - (float(page_total['value']) if page_total else 0):,.0f}, not {float(l['value']):,.0f}." if l else "",
                              ["SchC.44a", f"doc:D23#page{i+1}", "D23", "SchC.9"], None, "Adjust SchC.44a and the mileage deduction on SchC.9; mark page 3 as a duplicate."))
    # same W-2 twice
    a, b = p.doc_by_id.get("D09"), p.doc_by_id.get("D10")
    if a and b:
        va = {e["field"]: e["value"] for e in p.evs_by_doc["D09"]}
        vb = {e["field"]: e["value"] for e in p.evs_by_doc["D10"]}
        if va == vb:
            out.append(mk("duplicate_w2_image", "wages_and_stock_compensation", "D10 is a second image of the Halvorsen W-2 (D09)", "info",
                          "Every extracted box is identical. The engine counted it once (note on F1040.1a) but never marked it as a duplicate; D10's reads are lower confidence.", ["D09", "D10", "F1040.1a"], None, "Mark D10 as a duplicate of D09 so it never gets summed."))
    # same interest twice: composite 1099-INT section and stand-alone 1099-INT for the same sweep account
    l1, l2 = p.line("SchB.1.1", vid), p.line("SchB.1.2", vid)
    if l1 and l2 and l1["value"] == l2["value"] and "Northlake" in l1["label"] and "Northlake" in l2["label"]:
        eff2, adj2 = s.effective_value("SchB.1.2", l2["value"])
        out.append(mk("duplicate_interest_northlake", "investments_and_digital_assets", "Northlake sweep interest 1,840 reported twice", "pass" if adj2 else "fail",
                      "D28 (consolidated 1099, account ending 7731) carries the bank-sweep 1099-INT of 1,840 and D29 is the stand-alone Form 1099-INT from Northlake Bank for the same sweep program and account. The engine listed both as payers.",
                      ["SchB.1.1", "SchB.1.2", "ev-0492", "ev-0538", "D28", "D29"], None, "Remove one payer line (adjust SchB.1.2 to 0) and record D29 as a duplicate of the D28 section."))
    return out


@check
def t_client_statements_vs_engine(p: Packet, s: State, vid: str):
    """Things the client said that the engine ignored or contradicted."""
    out = []
    # SE health insurance while eligible for spouse's employer plan
    l = p.line("Sch1.17", vid)
    qa = p.qa_by_id.get("qa-25")
    if l and qa and str(qa["answer"]).lower().startswith("yes") and float(l["value"]) > 0:
        eff, adj = s.effective_value("Sch1.17", l["value"])
        out.append(mk("sehi_eligible_for_employer_plan", "business", "Self-employed health insurance deducted (14,400) although Erik was eligible for Ngozi's employer plan", "pass" if adj else "fail",
                      f"qa-25: '{qa['answer']}'. The deduction is not allowed for any month the taxpayer was eligible to participate in a subsidized employer plan (also the prior preparer's 2024 position, note on Sch1.17). The premiums may still count as a medical itemized deduction subject to the AGI floor.",
                      ["Sch1.17", "qa-25", "ev-0484", "D25", "py:/return_2024/notes/Sch1.17"], None, "Adjust Sch1.17 to 0 and record the judgment with authority (IRC 162(l)(2)(B))."))
    # mixed-use phone/internet and personal subscription
    call = p.call_by_id.get("call-01")
    if call:
        for key, label, share, src in [("SchC.25", "Telephone and internet", None, ["ev-0101", "ev-0095"])]:
            l = p.line(key, vid)
            if l:
                eff, adj = s.effective_value(key, l["value"])
                exp = 2160 * 0.7 + 1320 * 0.5
                out.append(mk("mixed_use_utilities", "business", "Telephone and internet deducted 100%; client says 70% and 50% business", "pass" if adj else "fail",
                              f"call-01: family mobile plan 70% business, home internet 50%. Engine took the books figures in full ({float(l['value']):,.0f}); the business share is about {exp:,.0f}.",
                              [key, "call-01", *src, "doc:D15#page2"], None, "Adjust SchC.25 to the business share and cite the call."))
        l = p.line("SchC.18", vid)
        if l:
            eff, adj = s.effective_value("SchC.18", l["value"])
        l27 = next((k for k, x in p.lines(vid).items() if x["form"] == "SchC" and "software" in x["label"].lower()), None)
        if l27:
            eff, adj = s.effective_value(l27, p.line(l27, vid)["value"])
            out.append(mk("personal_subscription_in_software", "business", "Spotify Family 216 (personal, per the client) is inside the software deduction", "pass" if adj else "warn",
                          "call-01: 'Spotify Family in software is personal - booked by mistake'. D15 page 1 lists it inside the 6,850.", [l27, "call-01", "doc:D15#page1", "ev-0099"], None, "Reduce the software line by 216."))
    # Q4 federal estimate: client guess vs IRS transcript
    l = p.line("F1040.26", vid)
    if l:
        tx = p.agency["irs_account_transcript_2025"][0]["transactions"]
        irs = sum(t["amount"] for t in tx if t["code"] == "670" and str(t["date"]) <= "2026-01-31")
        eff, adj = s.effective_value("F1040.26", l["value"])
        if abs(float(l["value"]) - irs) > 1:
            out.append(mk("estimates_vs_irs_transcript", "payments_and_penalties", f"Federal estimated payments {float(l['value']):,.0f} on the return vs {irs:,.0f} on the IRS transcript", "pass" if adj else "fail",
                          "The engine took the 4th-quarter payment from the client's answer ('4,000 I think', qa-41); EFTPS confirmations D67 cover only Q1-Q3 and the IRS transcript (D69) shows 3,000 paid 2026-01-15. Overstating payments by 1,000 understates the balance due and changes the Form 2210 penalty.",
                          ["F1040.26", "qa-41", "D67", "agency:/irs_account_transcript_2025/0", "F2210.19"], {"irs": irs}, "Adjust F1040.26 to the transcript figure (agreed_to_third_party_record) and ask the client for the Q4 confirmation."))
    # CA estimate designated to 2024
    l = p.line("F540NR.72", vid)
    yr = _ev(p, "D68", "pay5_year")
    if l and yr and str(yr["value"]) == "2024":
        eff, adj = s.effective_value("F540NR.72", l["value"])
        ftb = sum(x["amount"] for x in p.agency["ftb_account"]["tax_year_2025_payments"])
        out.append(mk("ftb_payment_designated_2024", "payments_and_penalties", "California estimated payments include the 2025-09-15 Web Pay of 3,500 that the client designated to tax year 2024", "pass" if adj else "fail",
                      f"D68 prints tax year 2024 on that confirmation ({yr['id']}) and the FTB account shows it held as a 2024 credit. FTB 2025 payments total {ftb:,.0f}; the engine used {float(l['value']):,.0f}. It also sits inside the SALT deduction (SchA.5a), where it does belong as a 2025 cash payment.",
                      ["F540NR.72", yr["id"], "ev-1075", "agency:/ftb_account", "SchA.5a"], {"ftb": ftb}, "Adjust F540NR.72 to the FTB figure; ask the client to have FTB move the payment to 2025 or claim it on an amended 2024."))
    # IRA basis: client says none, prior 8606 says 7,000
    qa = p.qa_by_id.get("qa-31")
    basis = p.prior_years["basis_records"].get("ira_nondeductible_basis_ngozi", [])
    if qa and basis and "none" in str(qa["answer"]).lower():
        out.append(mk("ira_basis_client_vs_prior_8606", "retirement_and_hsa", "Client says no prior IRA basis; the 2024 Form 8606 and Form 5498 show 7,000", "warn",
                      f"qa-31: '{qa['answer'][:80]}...' vs prior_years.basis_records (2024 Form 8606 line 14 = 7,000) and D42. The engine's F8606 should carry the prior basis; confirm which lines use it.", ["qa-31", "D42", "py:/basis_records/ira_nondeductible_basis_ngozi", "F8606.2"], None, "Agree F8606 line 2 to the 2024 Form 8606."))
    return out


@check
def t_document_vs_engine_values(p: Packet, s: State, vid: str):
    out = []
    # vehicle donation: 1098-C gross proceeds vs client's KBB estimate
    l = p.line("F8283.A1.vehicle", vid)
    gp = _ev(p, "D66", "box4c")
    if l and gp and float(l["value"]) > float(gp["value"]):
        eff, adj = s.effective_value("F8283.A1.vehicle", l["value"])
        out.append(mk("vehicle_donation_1098c", "deductions_and_credits", f"Donated car deducted at the client's estimate ({float(l['value']):,.0f}); Form 1098-C limits it to gross proceeds {float(gp['value']):,.0f}", "pass" if adj else "fail",
                      "The charity sold the 2012 Subaru at auction (qa-39, call-01). The engine cited the questionnaire instead of the Form 1098-C box 4c that is in the file.", ["F8283.A1.vehicle", gp["id"], "D66", "qa-39", "SchA.12"], None, "Adjust to 2,900 (code: sold without significant use) and attach the 1098-C to Form 8283."))
    # payoff interest already inside the 1098
    l = p.line("SchA.8a", vid)
    pay = _ev(p, "D56", "interest")
    if l and pay and "payoff" in (l.get("note") or "").lower():
        page = p.page("D55", 1)
        if page and "interest paid at payoff" in page["printed_content"]:
            eff, adj = s.effective_value("SchA.8a", l["value"])
            out.append(mk("payoff_interest_double_counted", "deductions_and_credits", "Lonestar payoff interest 2,150 added on top of a Form 1098 that already includes it", "pass" if adj else "fail",
                          "D55 box 1 (13,900) says it 'includes ... interest paid at payoff 11/20/2025', and D56 says the payoff interest 'is reported on the 2025 Form 1098'. The engine added the 2,150 again.", ["SchA.8a", "ev-1029", "ev-1032", "D55", "D56"], None, "Adjust SchA.8a down by 2,150."))
    # property tax: full-year bill vs seller credit at closing
    l = p.line("SchA.5b", vid)
    credit = _ev(p, "D54", "tax_credit")
    if l and credit and float(l["value"]) >= 13000:
        eff, adj = s.effective_value("SchA.5b", l["value"])
        out.append(mk("property_tax_seller_credit", "deductions_and_credits", "Full-year Travis County tax deducted although the seller credited the January-July share at closing", "pass" if adj else "fail",
                      f"The 1098 box 10 / receipt show {float(l['value']):,.0f} paid from escrow, but the buyer closing statement D54 (cited by no line) shows a seller credit of {float(credit['value']):,.0f} for 01/01-07/07/2025. Only {float(l['value']) - float(credit['value']):,.0f} is the buyers' tax.", ["SchA.5b", credit["id"], "D54", "D58", "ev-1036"], None, "Adjust SchA.5b to the net amount."))
    # HVAC replacement expensed
    l = p.line("SchE.14A", vid)
    inv = _ev(p, "D47", "total")
    if l and inv and "HVAC" in (l.get("note") or ""):
        eff, adj = s.effective_value("SchE.14A", l["value"])
        judged = any(n.get("target") in ("SchE.14A", "D47") and n.get("kind") in ("judgment", "election") for n in s.notes.values())
        out.append(mk("hvac_capital_vs_repair", "rentals_and_sale", "HVAC system replacement (11,000) expensed as a repair", "pass" if (adj or judged) else "fail",
                      "D47: removed the furnace and condenser, installed a new heat pump system with air handler and line set (permit pulled). Call-01: 'replaced the whole system'. That is a restoration/improvement of a building system, capitalized over 27.5 years, not a repair. The engine took the owner statement's 'repairs' bucket at face value.", ["SchE.14A", inv["id"], "D47", "call-01", "F4562-E.19h"], None, "Move 11,000 to a new 27.5-year asset placed in service 2025-08-12 (mid-month: 5 months); record the judgment with authority (Reg. 1.263(a)-3(k))."))
    # FX rate year
    l = p.line("SchB.1.6", vid)
    if l and any("2024_average" in x for x in l.get("sources") or []):
        eff, adj = s.effective_value("SchB.1.6", l["value"])
        sek = _ev(p, "D36", "interest_sek")
        exp = float(sek["value"]) / p.fx_rates["SEK_per_USD"]["2025_average"]
        out.append(mk("fx_rate_wrong_year", "investments_and_digital_assets", "Swedish interest converted at the 2024 average rate (10.56) instead of the 2025 average (9.86)", "pass" if adj else "fail",
                      f"SEK {float(sek['value']):,.0f} / 9.86 = {exp:,.0f}, engine {float(l['value']):,.0f}. The rate reference on the line says 2024_average.", ["SchB.1.6", "ev-0960", "ref:fx.SEK.2025_average", "ref:fx.SEK.2024_average"], {"expected": exp}, "Adjust SchB.1.6 to the 2025 average conversion."))
    # provider EIN transposed
    e = _ev(p, "D62", "ein")
    page = p.page("D62", 1)
    if e and page and str(e["value"]) not in page["printed_content"]:
        m = re.search(r"Tax ID ([\d-]+)", page["printed_content"])
        verified = any(v["target"] in (e["id"], "F2441.1b") for v in s.verifications)
        out.append(mk("provider_ein_transposed", "deductions_and_credits", f"Dependent care provider EIN read as {e['value']} but the statement prints {m.group(1) if m else '?'}", "pass" if verified else "fail",
                      f"Digit transposition at confidence {e['confidence']:.2f}. A wrong provider TIN on Form 2441 is an e-file reject / credit denial risk.", [e["id"], "D62", "F2441.1b"], None, "Verify against the statement and correct the provider TIN."))
    # Meridian unread page: the missing lot
    pg = p.page("D31", 32)
    if pg and "M18" in pg["printed_content"] and not any(k.endswith(".M18") for k in p.lines(vid)):
        added = any(a["line_key"].startswith("F8949") and "M18" in (a.get("reason") or "") for a in s.adjustments.values())
        out.append(mk("meridian_missing_lot_m18", "investments_and_digital_assets", "Lot M18 (Ironwood REIT, proceeds 250, basis 310) is on the unread Meridian page 32 and missing from Form 8949", "pass" if added else "fail",
                      "This is exactly the 250 summary-vs-lots gap the engine diagnosed but could not explain. A 60 short-term loss is missing.", ["doc:D31#page32", "ev-0703", "F8949.B.total"], None, "Add the lot as an adjustment citing the page."))
    return out


@check
def t_ca_column_d_consistency(p: Packet, s: State, vid: str):
    """Schedule CA column D must equal A - B + C."""
    out = []
    lines = p.lines(vid)
    for k, l in lines.items():
        m = re.match(r"^SchCA540NR\.(\d+[a-z]?)\.D$", k)
        if not m:
            continue
        n = m.group(1)
        a = lines.get(f"SchCA540NR.{n}.A", {}).get("value", 0) or 0
        b = lines.get(f"SchCA540NR.{n}.B", {}).get("value", 0) or 0
        c = lines.get(f"SchCA540NR.{n}.C", {}).get("value", 0) or 0
        if all(isinstance(x, (int, float)) for x in (a, b, c, l["value"])) and abs((a - b + c) - l["value"]) > 1:
            out.append(mk(f"ca_column_d:{n}", "california", f"Schedule CA line {n}: column D is not A - B + C", "warn", f"A {a:,} - B {b:,} + C {c:,} = {a-b+c:,} vs D {l['value']:,}.", [k, f"SchCA540NR.{n}.A"], None, "Trace the column D rule; the engine applied a California-law recomputation not shown as an addition or subtraction."))
    return out


@check
def t_post_v3_information(p: Packet, s: State, vid: str):
    """Client information that arrived after the last engine run and changes a number."""
    out = []
    v = p.version(vid)
    msg = p.msg_by_id.get("msg-07")
    l = p.line("F8949.H.C6", vid)
    if msg and l and msg["sent_at"] > v["computed_at"]:
        eff, adj = s.effective_value("F8949.H.C6", l["value"])
        out.append(mk("crypto_c6_basis_after_v3", "investments_and_digital_assets", "Crypto lot C6: client supplied a 2021 purchase (about 3,050) after v3; the return still carries zero basis", "pass" if adj else "fail",
                      f"msg-07 ({msg['sent_at'][:10]}) answers the engine's DIGITAL_ASSET_BASIS_MISSING diagnostic: bought March 2021, moved June 2021, so long-term with basis about 3,050, not short-term zero basis. Nothing recomputed before the client signed.", ["F8949.H.C6", "msg-07", "ev-0879", "D34", "D35"], None, "Adjust the lot (basis 3,050, long-term) and record the judgment on the uncorroborated basis."))
    # Theo's SSN card after v3 is covered by identity checks; St. Brigid confirmation verifies the low-confidence read
    m8 = p.msg_by_id.get("msg-08")
    if m8 and not any(x["target"] in ("ev-1049", "SchA.11") for x in s.verifications):
        out.append(mk("st_brigid_confirmed", "deductions_and_credits", "St. Brigid gift read at 0.41 confidence; the client's confirmation (1,500) is on file but not recorded as verification", "warn",
                      "msg-08: parish confirmed 1,500, bank check #2207. The engine's value happens to be right; the workpaper must still show how it was verified.", ["ev-1049", "SchA.11", "msg-08", "D64"], None, "Record 'confirmed_with_client' on ev-1049 citing msg-08."))
    return out
