"""The records a CPA expects, each generated from the graph rather than stored.

Every record returns rows with line keys / refs so the UI can trace any number.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Any

from .events import State
from .packet import Packet
from .service import Service

RECORD_LIST = [
    {"id": "summary", "title": "Return summary vs last year"},
    {"id": "tax_computation", "title": "Tax computation"},
    {"id": "areas", "title": "Area summaries"},
    {"id": "document_index", "title": "Document index"},
    {"id": "depreciation", "title": "Depreciation by asset"},
    {"id": "sales_detail", "title": "Sales detail (Form 8949)"},
    {"id": "books_to_tax", "title": "Books to tax (Schedule C)"},
    {"id": "rentals", "title": "Rentals and passive losses"},
    {"id": "k1", "title": "K-1 lines and basis"},
    {"id": "retirement_foreign", "title": "Retirement and foreign items"},
    {"id": "deductions_credits", "title": "Deductions and credits with limits"},
    {"id": "payments", "title": "Payments and agency records"},
    {"id": "state_split", "title": "State split (California)"},
    {"id": "carryovers", "title": "Carryovers"},
    {"id": "basis", "title": "Basis by year"},
    {"id": "prior_vs_us", "title": "Prior preparer vs what we changed"},
    {"id": "completeness", "title": "Completeness: documents, areas, outside filings"},
    {"id": "judgments", "title": "Judgment calls, elections, due diligence, penalties"},
    {"id": "signoffs", "title": "Sign-offs and review trail"},
    {"id": "notice_response", "title": "Notice response record"},
    {"id": "carryforward_plan", "title": "Carry forward and 2026 plan"},
]


def _eff(p: Packet, st: State, key: str, vid: str | None):
    l = p.line(key, vid)
    if not l:
        return None
    return st.effective_value(key, l["value"])[0]


def _rows_for_form(p: Packet, st: State, svc: Service, form: str, vid: str | None, jurisdiction: str | None = None) -> list[dict]:
    rows = []
    for k, l in p.lines(vid).items():
        if l["form"] != form or (jurisdiction and l["jurisdiction"] != jurisdiction):
            continue
        eff, adj = st.effective_value(k, l["value"])
        rows.append({"key": k, "line": l["line"], "label": l["label"], "value": eff, "engine_value": l["value"], "adjusted": adj is not None,
                     "sources": l.get("sources") or [], "inputs": l.get("inputs") or [], "note": l.get("note"), "prior": svc.prior_value(k)})
    return rows


def rec_summary(p: Packet, st: State, svc: Service, vid: str | None):
    return svc.return_summary(st, vid)


def rec_tax_computation(p: Packet, st: State, svc: Service, vid: str | None):
    return {"federal": _rows_for_form(p, st, svc, "F1040", vid), "schedule2": _rows_for_form(p, st, svc, "Sch2", vid), "schedule3": _rows_for_form(p, st, svc, "Sch3", vid),
            "amt": _rows_for_form(p, st, svc, "F6251", vid), "niit": _rows_for_form(p, st, svc, "F8960", vid), "addl_medicare": _rows_for_form(p, st, svc, "F8959", vid),
            "california": _rows_for_form(p, st, svc, "F540NR", vid), "rates": p.version(vid)["tax_effect_rates"], "parameters": p.engine["parameters"]}


def rec_areas(p: Packet, st: State, svc: Service, vid: str | None):
    from .checks import run_checks
    return svc.area_summaries(st, run_checks(p, st, vid), vid)


def rec_document_index(p: Packet, st: State, svc: Service, vid: str | None):
    return svc.document_index(st, vid)


def rec_depreciation(p: Packet, st: State, svc: Service, vid: str | None):
    v = p.version(vid)
    rows = []
    for a in v.get("assets", []):
        prior = p.prior_asset_by_id.get(a["asset_id"])
        rows.append({**a, "prior_record": prior, "history_federal": (prior or {}).get("federal"), "history_california": (prior or {}).get("california"),
                     "ref": f"asset:{a['asset_id']}"})
    return {"assets": rows, "forms": {"F4562-C": _rows_for_form(p, st, svc, "F4562-C", vid), "F4562-E": _rows_for_form(p, st, svc, "F4562-E", vid), "FTB3885A": _rows_for_form(p, st, svc, "FTB3885A", vid), "F4797": _rows_for_form(p, st, svc, "F4797", vid)},
            "ca_basis_differences": v.get("carryovers_out", {}).get("california", {}).get("depreciation_basis_differences")}


def rec_sales_detail(p: Packet, st: State, svc: Service, vid: str | None):
    """Hundreds of lots: aggregate by box and broker, exceptions first."""
    lots = []
    by_box: dict[str, dict] = defaultdict(lambda: {"count": 0, "proceeds": 0.0, "basis": 0.0, "gain": 0.0, "wash": 0.0})
    by_broker: dict[str, dict] = defaultdict(lambda: {"count": 0, "proceeds": 0.0, "basis": 0.0})
    for k, l in p.lines(vid).items():
        if not k.startswith("F8949."):
            continue
        box = k.split(".")[1]
        m = re.search(r"proceeds ([\d,\.]+), basis ([\d,\.]+)", l["label"])
        proceeds = float(m.group(1).replace(",", "")) if m else None
        basis = float(m.group(2).replace(",", "")) if m else None
        m2 = re.search(r"acquired ([\d-]+|various), sold ([\d-]+)", l["label"])
        acquired = m2.group(1) if m2 else None
        sold = m2.group(2) if m2 else None
        srcs = l.get("sources") or []
        doc = p.ev_by_id[srcs[0]]["document_id"] if srcs and srcs[0] in p.ev_by_id else None
        broker = p.doc_by_id[doc]["title"].split(" 2025")[0] if doc else "?"
        eff, adj = st.effective_value(k, l["value"])
        gain = (proceeds - basis) if proceeds is not None and basis is not None else None
        flags = []
        if basis == 0:
            flags.append("zero basis")
        if adj:
            flags.append("adjusted")
        if l.get("note"):
            flags.append("engine note")
        if sold and sold < "2025-07-15":
            flags.append("CA-source (sold before move)")
        if acquired and sold and acquired != "various":
            try:
                lt = (date.fromisoformat(sold) - date.fromisoformat(acquired)).days > 365
                if (box in ("A", "B") and lt) or (box in ("D", "E") and not lt):
                    flags.append("holding period vs box")
            except ValueError:
                pass
        row = {"key": k, "box": box, "label": l["label"], "value": eff, "proceeds": proceeds, "basis": basis, "gain": gain, "acquired": acquired, "sold": sold,
               "broker": broker, "document": doc, "sources": srcs, "flags": flags, "note": l.get("note")}
        lots.append(row)
        b = by_box[box]
        b["count"] += 1
        b["proceeds"] += proceeds or 0
        b["basis"] += basis or 0
        b["gain"] += gain or 0
        bb = by_broker[broker]
        bb["count"] += 1
        bb["proceeds"] += proceeds or 0
        bb["basis"] += basis or 0
    exceptions = [r for r in lots if r["flags"]]
    return {"count": len(lots), "by_box": by_box, "by_broker": by_broker, "exceptions": exceptions, "lots": lots,
            "schedule_d": _rows_for_form(p, st, svc, "SchD", vid), "carryover_in": p.prior_years["carryovers_into_2025"]}


def rec_books_to_tax(p: Packet, st: State, svc: Service, vid: str | None):
    books = p.evs_by_doc.get("D14", [])
    schc = _rows_for_form(p, st, svc, "SchC", vid)
    schc_by_label = {r["label"].lower(): r for r in schc}
    rows = []
    for e in books:
        lines = p.lines_citing_ev(e["id"], vid)
        tax_value = sum((_eff(p, st, k, vid) or 0) for k in lines) if lines else None
        rows.append({"books_label": e["label"], "books_value": e["value"], "ev": e["id"], "lines": lines, "tax_value": tax_value,
                     "difference": (tax_value - e["value"]) if tax_value is not None and isinstance(e["value"], (int, float)) else None, "confidence": e["confidence"]})
    third_party = {"1099-NEC": [{"doc": d, "value": [x["value"] for x in p.evs_by_doc[d] if "box 1" in x["label"].lower() or x["field"].lower().startswith("box 1")]} for d in ["D16", "D17", "D18", "D19", "D20"]],
                   "1099-K": [{"doc": "D21", "value": [x["value"] for x in p.evs_by_doc.get("D21", []) if x["field"].lower().startswith("box 1a")]}]}
    return {"books": rows, "schedule_c": schc, "se": _rows_for_form(p, st, svc, "SchSE", vid), "qbi": _rows_for_form(p, st, svc, "F8995", vid), "third_party": third_party,
            "client_statements": [p.call_by_id.get("call-01"), p.qa_by_id.get("qa-21"), p.qa_by_id.get("qa-22"), p.qa_by_id.get("qa-24")]}


def rec_rentals(p: Packet, st: State, svc: Service, vid: str | None):
    sche = _rows_for_form(p, st, svc, "SchE", vid)
    return {"schedule_e": sche, "passive": _rows_for_form(p, st, svc, "F8582", vid), "sale": _rows_for_form(p, st, svc, "F4797", vid),
            "carryover_in": {k: v for k, v in p.prior_years["carryovers_into_2025"].items() if "passive" in k}, "carryovers_out": p.version(vid).get("carryovers_out")}


def rec_k1(p: Packet, st: State, svc: Service, vid: str | None):
    return {"f7203": _rows_for_form(p, st, svc, "F7203", vid), "k1_documents": {d: p.evs_by_doc.get(d, []) for d in ["D37", "D38", "D39", "D40"]},
            "basis_records": p.prior_years["basis_records"], "prior_k1": {"1120S": p.prior_years["return_2024"].get("K1_1120S"), "1065": p.prior_years["return_2024"].get("K1_1065")},
            "schedule_e_p2": [r for r in _rows_for_form(p, st, svc, "SchE", vid) if r["line"].startswith(("28", "29", "30", "31", "32"))],
            "schedule_s": _rows_for_form(p, st, svc, "ScheduleS", vid)}


def rec_retirement_foreign(p: Packet, st: State, svc: Service, vid: str | None):
    return {"f8606": _rows_for_form(p, st, svc, "F8606", vid), "f8889": _rows_for_form(p, st, svc, "F8889", vid), "f8938": _rows_for_form(p, st, svc, "F8938", vid),
            "documents": {d: p.evs_by_doc.get(d, []) for d in ["D41", "D42", "D43", "D44", "D45", "D36", "D26"]}, "fx": p.fx_rates, "ira_basis": p.prior_years["basis_records"].get("ira_nondeductible_basis_ngozi")}


def rec_deductions_credits(p: Packet, st: State, svc: Service, vid: str | None):
    return {"schedule_a": _rows_for_form(p, st, svc, "SchA", vid), "f8283": _rows_for_form(p, st, svc, "F8283", vid), "f8812": _rows_for_form(p, st, svc, "F8812", vid),
            "f8863": _rows_for_form(p, st, svc, "F8863", vid), "f2441": _rows_for_form(p, st, svc, "F2441", vid), "f8867": _rows_for_form(p, st, svc, "F8867", vid),
            "schedule3": _rows_for_form(p, st, svc, "Sch3", vid), "limits": {k: p.engine["parameters"].get(k) for k in ["std_deduction_mfj", "salt_cap", "salt_cap_phase_start", "ctc_per_child", "odc_per_dependent", "ctc_phaseout_start", "aotc_phaseout", "dep_care_limit_one", "dep_care_exclusion_max"]}}


def rec_payments(p: Packet, st: State, svc: Service, vid: str | None):
    v = p.version(vid)
    pay_lines = [r for r in _rows_for_form(p, st, svc, "F1040", vid) if re.match(r"^(2[5-9]|3\d)", r["line"])]
    ca_pay = [r for r in _rows_for_form(p, st, svc, "F540NR", vid) if re.match(r"^(8\d|9\d|1\d\d)", r["line"])]
    return {"federal_lines": pay_lines, "california_lines": ca_pay, "irs_transcript": p.agency["irs_account_transcript_2025"], "ftb_account": p.agency["ftb_account"],
            "eftps": p.evs_by_doc.get("D67", []), "ftb_webpay": p.evs_by_doc.get("D68", []), "penalty": _rows_for_form(p, st, svc, "F2210", vid) + _rows_for_form(p, st, svc, "FTB5805", vid),
            "extension": p.what_if.get("extension"), "efile": p.agency["efile"], "post_filing_rates": p.post_filing_rates, "client_answer_q4": p.qa_by_id.get("qa-41")}


def rec_state_split(p: Packet, st: State, svc: Service, vid: str | None):
    rows = _rows_for_form(p, st, svc, "SchCA540NR", vid)
    grid: dict[str, dict] = defaultdict(dict)
    for r in rows:
        m = re.match(r"^(\d+[a-z]?)\.([A-E])$", r["line"])
        if m:
            grid[m.group(1)][m.group(2)] = r
        else:
            grid[r["line"]]["X"] = r
    return {"grid": grid, "f540nr": _rows_for_form(p, st, svc, "F540NR", vid), "schedule_s": _rows_for_form(p, st, svc, "ScheduleS", vid), "residency": p.household["residency"],
            "parameters": {k: p.engine["parameters"].get(k) for k in ["ca_resident_days", "year_days", "ca_std_deduction_mfj", "ca_personal_credit", "ca_dependent_credit"]},
            "wage_detail": {d: [e for e in p.evs_by_doc.get(d, []) if "box 1" in e["label"].lower() or "box 16" in e["label"].lower() or "box 17" in e["label"].lower() or "box 15" in e["label"].lower()] for d in ["D08", "D09", "D10"]}}


def rec_carryovers(p: Packet, st: State, svc: Service, vid: str | None):
    return {"into_2025": p.prior_years["carryovers_into_2025"], "out_of_2025": p.version(vid).get("carryovers_out"), "notes": st.carryforward_notes,
            "landing_lines": {k: _eff(p, st, k, vid) for k in ["SchD.6", "SchD.14", "F8582.1c", "F8582.3c", "F6251.11"] if p.line(k, vid)}}


def rec_basis(p: Packet, st: State, svc: Service, vid: str | None):
    return {"records": p.prior_years["basis_records"], "f7203": _rows_for_form(p, st, svc, "F7203", vid), "f8606": _rows_for_form(p, st, svc, "F8606", vid),
            "home": p.prior_years["basis_records"].get("home_7709_barton_ridge"), "closing": {"buyer": p.evs_by_doc.get("D54", []), "seller": p.evs_by_doc.get("D51", [])},
            "carryovers_out": p.version(vid).get("carryovers_out")}


def rec_prior_vs_us(p: Packet, st: State, svc: Service, vid: str | None):
    ppw = p.prior_years["prior_preparer_workpaper"]
    r24 = p.prior_years["return_2024"]
    changed = []
    for k in r24["lines"]:
        cur = _eff(p, st, k, vid)
        if cur is not None and cur != r24["lines"][k]:
            changed.append({"key": k, "label": r24["line_labels"].get(k, k), "2024": r24["lines"][k], "2025": cur})
    open_items = []
    for item in ppw.get("open_items_left_by_prior_preparer", []):
        status = "open"
        evidence = []
        il = item.lower()
        if "2023" in il and "k-1" in il:
            status, evidence = "resolved", ["D40", "F7203.1"]
        elif "5498" in il:
            status, evidence = "resolved", ["D42", "D43"]
        elif "square" in il:
            status, evidence = "resolved", ["D24", "SchC.30"]
        notes = [n for n in st.notes.values() if item[:30].lower() in n.get("text", "").lower()]
        if notes:
            status = "resolved" if all(n["status"] == "resolved" for n in notes) else "in_progress"
        open_items.append({"item": item, "status": status, "evidence": evidence, "notes": [n["id"] for n in notes]})
    return {"prior_preparer": r24["prepared_by"], "memo": ppw.get("summary_memo"), "notes": ppw.get("notes"), "open_items": open_items,
            "our_adjustments": [a for a in st.adjustments.values()], "judgments": [n for n in st.notes.values() if n.get("kind") in ("judgment", "election")],
            "prior_notes": r24.get("notes"), "lines_changed": changed}


def rec_completeness(p: Packet, st: State, svc: Service, vid: str | None):
    docs = svc.document_index(st, vid)
    from .checks import run_checks
    checks = run_checks(p, st, vid)
    areas = svc.area_summaries(st, checks, vid)
    outside = [
        {"filing": "FinCEN Form 114 (FBAR)", "status": "outside engagement; client files", "refs": ["F8938.1.max", "D36"], "due": "2026-10-15"},
        {"filing": "Forms 1099-NEC to two contractors (Lindqvist Studio)", "status": "not filed; client to file (late)", "refs": ["SchC.I", "SchC.J", "D27", "qa-23"], "due": "2026-02-02"},
        {"filing": "Oregon composite return (Woodworks)", "status": "filed by the S corporation", "refs": ["D39", "ScheduleS.credit"]},
        {"filing": "Arizona composite return (Ridgeline)", "status": "filed by the fund", "refs": ["D38"]},
        {"filing": "Ada's own Form 1040", "status": "prepared by Ada; checked 'can be claimed'", "refs": ["household:ada"]},
        {"filing": "Form 3520 for 2023 inheritance (prior-year open item)", "status": "unresolved from prior preparer", "refs": ["py:/prior_preparer_workpaper/open_items_left_by_prior_preparer/3"]},
    ]
    questionnaire_coverage = []
    for q in p.client["questionnaire"]:
        cites = [l["key"] for l in p.lines(vid).values() if q["id"] in (l.get("sources") or [])]
        questionnaire_coverage.append({"id": q["id"], "question": q["question"], "answer": q["answer"], "lines": cites})
    return {"documents": {"total": len(docs), "used": sum(1 for d in docs if d["used_by_engine"]), "reference_only": sum(1 for d in docs if d["why_not"] and "reference" in d["why_not"]),
                          "unused": [d for d in docs if not d["used_by_engine"] and not d["superseded"]], "superseded": [d["id"] for d in docs if d["superseded"]],
                          "not_extracted": [d["id"] for d in docs if d["extraction_status"] == "not_extracted"], "partial": [d["id"] for d in docs if d["extraction_status"] == "partial"]},
            "areas": areas, "outside_filings": outside, "questionnaire": questionnaire_coverage,
            "required_steps": [c for c in checks if c["id"].startswith("step:")]}


def rec_judgments(p: Packet, st: State, svc: Service, vid: str | None):
    kinds = ("judgment", "election", "due_diligence", "penalty")
    return {"items": [n for n in st.notes.values() if n.get("kind") in kinds], "engine_elections": p.what_if["alternatives"],
            "due_diligence_required_for": ["child tax credit", "credit for other dependents"], "f8867": _rows_for_form(p, st, svc, "F8867", vid)}


def rec_signoffs(p: Packet, st: State, svc: Service, vid: str | None):
    return {"signoffs": list(st.signoffs.values()), "verifications": st.verifications, "adjustments": list(st.adjustments.values()), "filing": st.filing,
            "client_approvals": st.client_approvals, "notes": list(st.notes.values()), "questions": list(st.questions.values())}


def rec_notice_response(p: Packet, st: State, svc: Service, vid: str | None):
    """A self-contained record answering each item under examination."""
    out = []
    for n in p.agency["notices"]:
        items = []
        for item in n.get("items_under_examination", []):
            il = item.lower()
            keys = []
            if "8283" in il or "noncash" in il:
                keys = [k for k in p.lines(vid) if k.startswith("F8283") or k in ("SchA.12",)]
                docs = ["D65", "D66"]
            elif "schedule c" in il or "gross receipts" in il:
                keys = [k for k in p.lines(vid) if k in ("SchC.1", "SchC.7")]
                docs = ["D14", "D16", "D17", "D18", "D19", "D20", "D21"]
            else:
                docs = []
            evidence = []
            for k in keys:
                lv = svc.line_view(k, st, vid)
                evidence.append({"line": k, "label": lv["label"], "value": lv["value"], "sources": lv["sources"], "verifications": lv["verifications"], "adjustment": lv["adjustment"], "notes": lv["notes"]})
            items.append({"item": item, "lines": evidence, "documents": [{"id": d, "title": p.doc_by_id[d]["title"]} for d in docs],
                          "attachments": [a for a in st.attachments.values() if a["target"] in keys + docs], "client_statements": [p.qa_by_id.get("qa-39"), p.call_by_id.get("call-01")] if "8283" in il else [p.qa_by_id.get("qa-24"), p.qa_by_id.get("qa-22")]})
        out.append({**n, "items": items})
    return {"notices": out, "frozen_filing": st.filing}


def rec_carryforward_plan(p: Packet, st: State, svc: Service, vid: str | None):
    v = p.version(vid)
    return {"carryovers_out": v.get("carryovers_out"), "planning_2026": p.planning_2026, "assets_continuing": [a for a in v.get("assets", []) if not a.get("disposed")],
            "basis_end": {"scorp": v.get("carryovers_out", {}).get("federal", {}).get("scorp_stock_basis_end"), "ridgeline_capital": v.get("carryovers_out", {}).get("federal", {}).get("ridgeline_capital_account_end"),
                          "ira_basis": v.get("carryovers_out", {}).get("federal", {}).get("ira_nondeductible_basis_ngozi")},
            "open_items_for_next_year": [n for n in st.notes.values() if n["status"] == "open"] + [{"text": q["text"], "kind": "question", "status": q["status"]} for q in st.questions.values() if q["status"] == "open"],
            "notes": st.carryforward_notes, "total_tax_2025": {"federal": svc.working_summary(st, vid)["federal"]["total_tax_working"], "california": svc.working_summary(st, vid)["california"]["total_tax_working"]},
            "safe_harbor_110pct": round(svc.working_summary(st, vid)["federal"]["total_tax_working"] * 1.1)}
