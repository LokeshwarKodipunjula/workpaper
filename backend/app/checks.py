"""Independent checks: they do not trust the engine.

Each check returns dicts: {id, area, title, status: pass|fail|warn|info, message,
refs: [...], detail: {...}, action: str}. Structural checks run over the whole
packet; targeted checks encode the specific traps a reviewer must catch for
this household. Check overrides (accepted/waived with a reason) come from the
event log and are applied by the caller.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Callable

from .events import State
from .packet import Packet

Check = dict[str, Any]
CHECKS: list[Callable[[Packet, State, str], list[Check]]] = []


def check(fn):
    CHECKS.append(fn)
    return fn


def mk(id: str, area: str, title: str, status: str, message: str, refs: list[str] | None = None, detail: Any = None, action: str = "") -> Check:
    return {"id": id, "area": area, "title": title, "status": status, "message": message, "refs": refs or [], "detail": detail, "action": action}


def _num(x: Any) -> float | None:
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    return None


def parse_text_as_read(text: str, value_type: str) -> float | None:
    """Parse what was printed into a number the way a careful human would."""
    if text is None:
        return None
    t = str(text).strip()
    if not t:
        return None
    neg = t.startswith("(") and t.endswith(")") or t.startswith("-")
    t = t.strip("()").replace("$", "").replace("USD", "").replace("SEK", "").replace("%", "").strip()
    t = t.replace("−", "-").lstrip("-").strip()  # U+2212 minus sign, seen on bank statements
    # Swedish style "12 345,67"
    if re.match(r"^\d{1,3}( \d{3})*(,\d+)?$", t):
        t = t.replace(" ", "").replace(",", ".")
    elif re.match(r"^\d{1,3}(\.\d{3})+,\d+$", t):
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", "").replace(" ", "")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v



def _signed_combo_matches(vals: list[float], target: float, tol: float = 1.0) -> bool:
    """R-SUM lines may subtract some inputs (AGI = income - adjustments). Accept any +/- combination
    with the first input positive, or a plain sum, or the first input alone (floors/limits)."""
    from itertools import product
    if abs(sum(vals) - target) <= tol:
        return True
    if len(vals) > 10:
        return True  # too many to enumerate; other checks cover these
    for first in (1, -1):
        for signs in product((1, -1), repeat=len(vals) - 1):
            total = first * vals[0] + sum(sg * x for sg, x in zip(signs, vals[1:]))
            if abs(total - target) <= tol:
                return True
    return False


# ----------------------------------------------------------------------------- structural

@check
def c_text_vs_value(p: Packet, s: State, vid: str) -> list[Check]:
    out = []
    for e in p.extracted_values:
        if e["value_type"] not in ("money", "integer", "quantity", "percent"):
            continue
        parsed = parse_text_as_read(e["text_as_read"], e["value_type"])
        v = _num(e["value"])
        if parsed is None or v is None:
            continue
        if abs(parsed - v) > 0.011:
            lines = p.lines_citing_ev(e["id"], vid)
            out.append(mk(f"ev_text_mismatch:{e['id']}", p.area_of_document(e["document_id"]),
                          f"Extracted value disagrees with what is printed ({e['document_id']} {e['label']})",
                          "fail" if lines else "warn",
                          f"Pipeline read {e['value']:,} but the page prints '{e['text_as_read']}' (confidence {e['confidence']:.2f}). "
                          + (f"Flows into {', '.join(lines)}." if lines else "Not used by any line."),
                          [e["id"], e["document_id"], *lines], {"ev": e, "parsed": parsed},
                          "Agree the value to the source page and adjust the dependent line."))
    return out


@check
def c_low_confidence(p: Packet, s: State, vid: str) -> list[Check]:
    out = []
    for e in p.extracted_values:
        if e["confidence"] < 0.7:
            lines = p.lines_citing_ev(e["id"], vid)
            verified = any(v["target"] == e["id"] for v in s.verifications)
            out.append(mk(f"low_confidence:{e['id']}", p.area_of_document(e["document_id"]),
                          f"Low-confidence read ({e['confidence']:.2f}): {e['label']}",
                          "pass" if verified else ("warn" if lines else "info"),
                          f"{e['document_id']} page {e['page']}: read '{e['text_as_read']}' as {e['value']}." + (f" Used by {', '.join(lines)}." if lines else " Not used by any line."),
                          [e["id"], e["document_id"], *lines], {"ev": e}, "Verify against the page (or the client) and record the verification."))
    return out


@check
def c_sources_sum(p: Packet, s: State, vid: str) -> list[Check]:
    """Lines whose rule is a plain pass-through/sum of their extracted sources must equal them."""
    out = []
    sum_rules = {"R-W2-BOX1-SUM", "R-W2-BOX2-SUM", "R-W2-BOX17-SUM", "R-INTEREST-PAYER", "R-DIV-PAYER", "R-SUM", "R-CARRY", "R-1099NEC-SUM", "R-COPY"}
    for l in p.lines(vid).values():
        srcs = [x for x in (l.get("sources") or []) if x.startswith("ev-")]
        if not srcs or l.get("inputs"):
            continue
        v = _num(l["value"])
        if v is None:
            continue
        vals = [_num(p.ev_by_id[x]["value"]) for x in srcs if x in p.ev_by_id]
        if any(x is None for x in vals) or not vals:
            continue
        total = sum(vals)
        rule = l.get("rule", "")
        if rule in sum_rules:
            tol = 1.0 if not l["key"].startswith("F8949") else 1.0
            if abs(total - v) > tol:
                # a single source may legitimately be partially used (e.g. a box used after limit) -> warn
                out.append(mk(f"source_sum:{l['key']}", p.area_of_line(l["key"]), f"Line {l['key']} does not equal its cited sources",
                              "warn", f"{l['label']}: engine {v:,.0f} vs sum of cited values {total:,.2f} (rule {rule}).",
                              [l["key"], *srcs], {"sources": vals}, "Trace the line and confirm which source the engine used."))
    return out


@check
def c_inputs_sum(p: Packet, s: State, vid: str) -> list[Check]:
    out = []
    for l in p.lines(vid).values():
        if l.get("rule") != "R-SUM" or not l.get("inputs"):
            continue
        if re.match(r"^SchCA540NR\.\d+[a-z]?\.D$", l["key"]):
            continue  # column D = A - B + C is checked by t_ca_column_d_consistency
        v = _num(l["value"])
        vals = [_num(p.line(k, vid)["value"]) for k in l["inputs"] if p.line(k, vid)]
        if v is None or any(x is None for x in vals) or len(vals) != len(l["inputs"]):
            continue
        if not _signed_combo_matches(vals, v):
            out.append(mk(f"input_sum:{l['key']}", p.area_of_line(l["key"]), f"Line {l['key']} is not the sum of its inputs", "fail",
                          f"{l['label']}: engine {v:,.0f} vs sum of inputs {sum(vals):,.0f}.", [l["key"], *l["inputs"]], None, "Recalculate; the engine's arithmetic is wrong here."))
    return out


@check
def c_summary_vs_lines(p: Packet, s: State, vid: str) -> list[Check]:
    v = p.version(vid)
    pairs = [("federal", "agi", "F1040.11"), ("federal", "taxable_income", "F1040.15"), ("federal", "total_tax", "F1040.24"), ("federal", "payments", "F1040.33")]
    out = []
    for jur, k, line in pairs:
        l = p.line(line, vid)
        if l and _num(l["value"]) is not None and abs(float(l["value"]) - float(v["summary"][jur][k])) > 1:
            out.append(mk(f"summary_vs_line:{k}", "return_summary", f"Summary {k} disagrees with {line}", "fail",
                          f"summary {v['summary'][jur][k]:,} vs line {l['value']:,}", [line], None, "Recalculate the summary."))
    if not out:
        out.append(mk("summary_vs_lines", "return_summary", "Return summary agrees to Form 1040 lines", "pass", "AGI, taxable income, total tax and payments agree.", ["F1040.11", "F1040.15", "F1040.24", "F1040.33"]))
    return out


@check
def c_documents_unused(p: Packet, s: State, vid: str) -> list[Check]:
    out = []
    v = p.version(vid)
    for d in p.documents:
        landed = p.where_document_landed(d["id"], vid)
        if landed["superseded"] or d["extraction"]["status"] == "not_extracted":
            continue
        if not landed["used_by_engine"]:
            out.append(mk(f"doc_unused:{d['id']}", p.area_of_document(d["id"]), f"{d['id']} received but not used by {vid}", "warn",
                          f"{d['title']} received {d['received_at'][:10]}; {vid} computed {v['computed_at'][:10]}. {landed['why_not']}",
                          [d["id"]], None, "Decide whether the return must be recomputed with it, or record why it is reference only."))
        elif landed["values_total"] and landed["values_landed"] == 0:
            out.append(mk(f"doc_reference_only:{d['id']}", p.area_of_document(d["id"]), f"{d['id']} is in the file but no line cites it", "info",
                          f"{d['title']}: {landed['values_total']} values extracted, none cited by a return line.", [d["id"]], None,
                          "Confirm it is reference only (or that its figures were meant to land somewhere)."))
    return out


@check
def c_partial_extraction(p: Packet, s: State, vid: str) -> list[Check]:
    out = []
    for d in p.documents:
        if d["extraction"]["status"] == "partial":
            missing = [int(x) for x in re.findall(r"[Pp]age (\d+)", d["extraction"].get("reason") or "")]
            status = "info" if d["id"] in p.version(vid).get("documents_superseded", []) else "fail"
            out.append(mk(f"partial_extraction:{d['id']}", p.area_of_document(d["id"]), f"{d['id']}: pages not read by the pipeline", status,
                          f"{d['title']}: {d['extraction'].get('reason')} Unread pages: {missing}.", [d["id"]] + [f"doc:{d['id']}#page{m}" for m in missing], None,
                          "Open the unread page and enter its figures as adjustments with the page as evidence."))
    return out


@check
def c_version_changes_declared(p: Packet, s: State, vid: str) -> list[Check]:
    out = []
    versions = p.versions
    for i in range(1, len(versions)):
        a, b = versions[i - 1], versions[i]
        la = {l["key"]: l["value"] for l in a["lines"]}
        lb = {l["key"]: l["value"] for l in b["lines"]}
        actual = {k for k in set(la) | set(lb) if la.get(k) != lb.get(k)}
        declared = {c["key"] for c in b.get("changes_from_previous", [])}
        missing = sorted(actual - declared)
        extra = sorted(declared - actual)
        if missing or extra:
            out.append(mk(f"changes_declared:{b['version']}", "return_summary", f"{b['version']} change list is incomplete", "warn",
                          f"{len(missing)} lines changed but not declared; {len(extra)} declared but unchanged.", missing[:20] + extra[:20],
                          {"undeclared": missing, "declared_unchanged": extra}, "Review the undeclared changes."))
    return out


@check
def c_identity(p: Packet, s: State, vid: str) -> list[Check]:
    out = []
    # SSNs on documents vs organizer
    people = p.household["people"]
    by_ssn_person = {x["id"]: x["ssn"] for x in people}
    for e in p.extracted_values:
        if e["value_type"] != "ssn":
            continue
        d = p.doc_by_id[e["document_id"]]
        who = d["belongs_to"].replace("dependent:", "")
        if who in by_ssn_person:
            if str(e["value"]).replace("-", "") != str(by_ssn_person[who]).replace("-", ""):
                out.append(mk(f"ssn_mismatch:{e['id']}", "intake_and_engagement", f"SSN on {e['document_id']} differs from the organizer ({who})", "fail",
                              f"{d['title']} prints {e['value']} but the household entry has {by_ssn_person[who]}.", [e["id"], e["document_id"], f"household:{who}"], None,
                              "Correct the household entry from the document (identity verification) before e-filing."))
    # prior year dependents SSN vs organizer
    for dep in p.prior_years["return_2024"].get("dependents", []):
        match = next((x for x in people if x["name"] == dep["name"]), None)
        if match and match["ssn"] != dep["ssn"]:
            out.append(mk(f"ssn_prior_year:{match['id']}", "intake_and_engagement", f"{match['name']}: SSN differs from the 2024 return", "fail",
                          f"Organizer {match['ssn']} vs 2024 return {dep['ssn']}. One of them is a typo; the e-file database will reject a mismatch.",
                          [f"household:{match['id']}", "py:/return_2024/dependents"], None, "Verify against the Social Security card and fix before e-filing."))
    # AGI for e-signature
    agi24 = p.prior_years["return_2024"]["lines"].get("F1040.11")
    if agi24 is not None and abs(float(agi24) - float(p.household["prior_year_agi_for_esignature"])) > 0.5:
        out.append(mk("esign_agi", "payments_and_penalties", "Prior-year AGI for e-signature does not match the 2024 return", "fail",
                      f"{p.household['prior_year_agi_for_esignature']} vs 2024 F1040.11 {agi24}", ["py:/return_2024/lines/F1040.11"], None, "Correct before e-filing."))
    else:
        out.append(mk("esign_agi", "payments_and_penalties", "Prior-year AGI for e-signature agrees to the 2024 return", "pass", f"{agi24:,}", ["py:/return_2024/lines/F1040.11"]))
    return out


@check
def c_questionnaire_conflicts(p: Packet, s: State, vid: str) -> list[Check]:
    out = []
    qa = p.qa_by_id
    n_sales = sum(1 for k in p.lines(vid) if k.startswith("F8949."))
    if qa.get("qa-14") and str(qa["qa-14"]["answer"]).strip().lower().startswith("no") and n_sales:
        out.append(mk("qa_sales_conflict", "investments_and_digital_assets", "Client said no investments were sold; the documents show sales", "warn",
                      f"qa-14 answer 'No' vs {n_sales} Form 8949 lots from three brokerages and the crypto exchange.", ["qa-14", "D28", "D31", "D74", "D34"], None,
                      "Confirm with the client and record the answer as evidence; it also bears on completeness (any other account?)."))
    return out


@check
def c_variances(p: Packet, s: State, vid: str) -> list[Check]:
    from .service import Service
    svc = Service(p)
    std = svc.standards(s)
    out = []
    explained = {n["target"] for n in s.notes.values() if n.get("kind") == "variance"}
    for k in p.lines(vid):
        l = p.line(k, vid)
        eff, _ = s.effective_value(k, l["value"])
        var = svc.variance(k, eff, std)
        if var and var["flagged"] and not k.startswith("F8949"):
            out.append(mk(f"variance:{k}", p.area_of_line(k), f"Swing from 2024: {l['label']}", "pass" if k in explained else "warn",
                          f"2024 {var['prior']:,} -> 2025 {eff:,} ({var['pct']:+.0f}%).", [k], var, "Explain the swing (job change, move, sale, ISO exercise, late K-1) in a variance note."))
    return out


@check
def c_required_steps(p: Packet, s: State, vid: str) -> list[Check]:
    """Firm required steps mapped to evidence in the event log."""
    out = []
    done = {n.get("step") for n in s.notes.values() if n.get("kind") == "required_step" and n["status"] == "resolved"}
    for step in p.firm["starter_standards"]["required_steps"]:
        auto = None
        if step == "Reviewer sign-off":
            auto = any(x["level"] == "reviewer" and x["scope"] == "return" for x in s.active_signoffs())
        elif step == "Partner sign-off":
            auto = any(x["level"] == "partner" and x["scope"] == "return" for x in s.active_signoffs())
        elif step == "Client approval and e-file authorization":
            auto = any(a.get("approved") for a in s.client_approvals)
        elif step == "Diagnostics resolved":
            auto = all(f"diag:{d['code']}" in s.check_overrides or d["severity"] == "info" for d in p.version(vid).get("diagnostics", []))
        ok = auto if auto is not None else (step in done)
        out.append(mk(f"step:{step}", "return_summary", f"Required step: {step}", "pass" if ok else "info", "Complete" if ok else "Not yet recorded", [], {"step": step},
                      "Record completion when done."))
    return out


@check
def c_engine_diagnostics(p: Packet, s: State, vid: str) -> list[Check]:
    out = []
    for d in p.version(vid).get("diagnostics", []):
        out.append(mk(f"diag:{d['code']}", p.area_of_line(d["refs"][0]) if d.get("refs") and p.line(d["refs"][0], vid) else (
            p.area_of_document(p.ev_by_id[d["refs"][0]]["document_id"]) if d.get("refs") and d["refs"][0] in p.ev_by_id else "return_summary"),
            f"Engine diagnostic {d['code']}", "warn" if d["severity"] == "warning" else "info", d["message"], d.get("refs", []), d, "Resolve and record the decision."))
    return out


def run_checks(p: Packet, s: State, vid: str | None = None) -> list[Check]:
    from . import checks_targeted  # noqa: F401  (registers the targeted checks)
    vid = vid or p.latest_version_id
    results: list[Check] = []
    for fn in CHECKS:
        try:
            results.extend(fn(p, s, vid))
        except Exception as exc:  # a broken check must never hide the others
            results.append(mk(f"check_error:{fn.__name__}", "return_summary", f"Check {fn.__name__} failed to run", "warn", str(exc)))
    proposed = {x["line_key"] for x in s.adjustments.values() if x["status"] == "proposed"}
    for r in results:
        if r["status"] == "fail" and any(ref in proposed for ref in r["refs"][:2]):
            r["status"] = "warn"
            r["message"] += " A correction has been proposed and is awaiting partner approval."
        ov = s.check_overrides.get(r["id"])
        if ov:
            r["override"] = ov
            r["raw_status"] = r["status"]
            if r["status"] in ("fail", "warn", "info"):
                r["status"] = "accepted" if ov["status"] == "accepted" else "waived"
    order = {"fail": 0, "warn": 1, "info": 2, "accepted": 3, "waived": 4, "pass": 5}
    results.sort(key=lambda r: (order.get(r["status"], 9), r["area"], r["title"]))
    return results
