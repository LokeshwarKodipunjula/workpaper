"""Read models: packet + event state folded into what the UI shows."""
from __future__ import annotations

import copy
import re
from collections import defaultdict
from typing import Any

from .events import State, fingerprint
from .packet import AREAS, Packet

# Line categories for tax-effect estimation (README: multiply change by the matching rate).
CATEGORY_RULES: list[tuple[str, str]] = [
    (r"^F1040\.1", "wages"), (r"^SchB\.", "interest"), (r"^F1040\.2", "interest"), (r"^F1040\.3", "interest"),
    (r"^SchC\.", "schc_profit"), (r"^SchSE", "schc_profit"),
    (r"^F8949\.[AB]", "stcg"), (r"^F8949\.[DE]", "ltcg"), (r"^SchD\.(1|2|3|4|5|6|7)", "stcg"), (r"^SchD\.", "ltcg"), (r"^F4797", "ltcg"),
    (r"^Sch1\.(1|2|3|4|5|6|7|8|9|10)", "ordinary_income"), (r"^SchE\.", "ordinary_income"), (r"^F8606", "ordinary_income"), (r"^F1040\.4", "ordinary_income"),
    (r"^Sch1\.(1[1-9]|2\d)", "adjustment"), (r"^F8889", "adjustment"),
    (r"^SchA\.(5|6|7)", "salt"), (r"^SchA\.", "itemized"), (r"^F8283", "itemized"),
    (r"^SchCA540NR", "ca_source_income"), (r"^F540NR", "ca_source_income"),
]


def category_for(key: str) -> str:
    for pat, cat in CATEGORY_RULES:
        if re.match(pat, key):
            return cat
    return "ordinary_income"


def tax_effect(packet: Packet, key: str, old: Any, new: Any, vid: str | None = None, category: str | None = None) -> dict[str, Any]:
    cat = category or category_for(key)
    rates = packet.version(vid)["tax_effect_rates"].get(cat) or {"federal_per_dollar": 0, "california_per_dollar": 0}
    try:
        delta = float(new) - float(old)
    except (TypeError, ValueError):
        delta = 0.0
    delta_dollars = delta  # Form 8949 lots carry cents precision but are dollar amounts
    # payments and credits change tax/balance 1:1
    one_to_one = re.match(r"^(F1040\.(2[5-9]|3[0-3])|Sch3\.|F540NR\.(8|9))", key) is not None
    fed = -delta_dollars if one_to_one else delta_dollars * rates["federal_per_dollar"]
    ca = 0.0 if (one_to_one and key.startswith("F1040")) else (-delta_dollars if one_to_one else delta_dollars * rates["california_per_dollar"])
    return {"category": cat, "delta": delta_dollars, "federal": round(fed), "california": round(ca),
            "rates": rates, "requires_partner": abs(fed) > 1000 or abs(ca) > 1000}


PRIOR_KEY_MAP = {  # 2024 keys that moved
    "CA540.13": "F540NR.13", "CA540.17": "F540NR.17", "CA540.18": "F540NR.18", "CA540.19": "F540NR.19",
    "CA540.31": "F540NR.31", "CA540.64": "F540NR.64", "CA540.71": "F540NR.71", "CA540.72": "F540NR.72",
}


class Service:
    def __init__(self, packet: Packet):
        self.p = packet

    # ---------------------------------------------------------------- lines
    def prior_value(self, key: str) -> Any:
        lines = self.p.prior_years["return_2024"]["lines"]
        if key in lines:
            return lines[key]
        for k24, k25 in PRIOR_KEY_MAP.items():
            if k25 == key:
                return lines.get(k24)
        return None

    def variance(self, key: str, value: Any, standards: dict) -> dict | None:
        prior = self.prior_value(key)
        if prior is None or not isinstance(prior, (int, float)) or not isinstance(value, (int, float)):
            return None
        delta = float(value) - float(prior)
        pct = (delta / abs(float(prior)) * 100) if prior else (100.0 if delta else 0.0)
        vr = standards.get("variance_review", {})
        flagged = abs(pct) > vr.get("flag_if_change_over_percent", 10) and abs(delta) > vr.get("and_over_amount", 1000)
        return {"prior": prior, "delta": round(delta, 2), "pct": round(pct, 1), "flagged": flagged}

    def standards(self, state: State) -> dict:
        std = copy.deepcopy(self.p.firm["starter_standards"])
        for path, ov in state.standards_overrides.items():
            cur = std
            parts = path.split(".")
            for part in parts[:-1]:
                cur = cur.setdefault(part, {})
            cur[parts[-1]] = ov["value"]
        return std

    def line_view(self, key: str, state: State, vid: str | None = None, standards: dict | None = None) -> dict | None:
        l = self.p.line(key, vid)
        if not l:
            return None
        standards = standards or self.standards(state)
        eff, adj = state.effective_value(key, l["value"])
        verifs = [v for v in state.verifications if v["target"] == key]
        notes = [n for n in state.notes.values() if n["target"] == key]
        questions = [q for q in state.questions.values() if q["target"] == key]
        attachments = [a for a in state.attachments.values() if a["target"] == key]
        pending = [a for a in state.adjustments.values() if a["line_key"] == key and a["status"] == "proposed"]
        return {
            **l,
            "engine_value": l["value"],
            "value": eff,
            "adjusted": adj is not None,
            "adjustment": adj,
            "pending_adjustments": pending,
            "area": self.p.area_of_line(key),
            "verifications": verifs,
            "verified": bool(verifs),
            "notes": notes,
            "open_notes": sum(1 for n in notes if n["status"] == "open"),
            "questions": questions,
            "attachments": attachments,
            "variance": self.variance(key, eff, standards),
            "dependents": self.p.dependents(key, vid),
            "source_count": len(l.get("sources") or []),
            "category": category_for(key),
        }

    def lines_view(self, state: State, vid: str | None = None, area: str | None = None, form: str | None = None) -> list[dict]:
        standards = self.standards(state)
        out = []
        for k, l in self.p.lines(vid).items():
            if area and self.p.area_of_line(k) != area:
                continue
            if form and l["form"] != form:
                continue
            out.append(self.line_view(k, state, vid, standards))
        return out

    # ---------------------------------------------------------------- sign-off fingerprints
    def scope_keys(self, scope: str, vid: str | None = None) -> list[str]:
        if scope == "return":
            return list(self.p.lines(vid).keys())
        return [k for k in self.p.lines(vid) if self.p.area_of_line(k) == scope]

    def scope_fingerprint(self, scope: str, state: State, vid: str | None = None) -> str:
        items = []
        for k in self.scope_keys(scope, vid):
            l = self.p.line(k, vid)
            eff, _ = state.effective_value(k, l["value"])
            items.append((k, eff))
        items.append(("__version__", vid or self.p.latest_version_id))
        return fingerprint(items)

    # ---------------------------------------------------------------- areas
    def area_summaries(self, state: State, checks: list[dict], vid: str | None = None) -> list[dict]:
        standards = self.standards(state)
        by_area: dict[str, dict] = {}
        for a in AREAS:
            by_area[a.id] = {
                "id": a.id, "title": a.title, "description": a.description, "budget_hours": a.budget_hours,
                "lines": 0, "verified": 0, "adjusted": 0, "flagged_variances": 0, "open_notes": 0, "blocking_notes": 0,
                "open_questions": 0, "checks_failing": 0, "checks_warning": 0, "documents": len(a.document_ids),
                "hours_logged": 0.0, "signoffs": [], "assignment": state.assignments.get(a.id),
            }
        for k, l in self.p.lines(vid).items():
            aid = self.p.area_of_line(k)
            s = by_area[aid]
            s["lines"] += 1
            eff, adj = state.effective_value(k, l["value"])
            if adj:
                s["adjusted"] += 1
            if any(v["target"] == k for v in state.verifications):
                s["verified"] += 1
            var = self.variance(k, eff, standards)
            if var and var["flagged"]:
                s["flagged_variances"] += 1
        for n in state.notes.values():
            if n["status"] == "open" and n.get("area") in by_area:
                by_area[n["area"]]["open_notes"] += 1
                if n.get("blocking"):
                    by_area[n["area"]]["blocking_notes"] += 1
        for q in state.questions.values():
            if q["status"] == "open" and q.get("area") in by_area:
                by_area[q["area"]]["open_questions"] += 1
        for c in checks:
            if c["area"] in by_area:
                if c["status"] == "fail":
                    by_area[c["area"]]["checks_failing"] += 1
                elif c["status"] == "warn":
                    by_area[c["area"]]["checks_warning"] += 1
        for t in state.time_entries:
            if t.get("area") in by_area:
                by_area[t["area"]]["hours_logged"] += float(t.get("hours", 0))
        for so in state.signoffs.values():
            if so["scope"] in by_area:
                by_area[so["scope"]]["signoffs"].append({"level": so["level"], "status": so["status"], "actor": so["actor"], "at": so["at"], "id": so["id"]})
        for s in by_area.values():
            s["status"] = self._area_status(s)
        return list(by_area.values())

    @staticmethod
    def _area_status(s: dict) -> str:
        if s["blocking_notes"] or s["checks_failing"]:
            return "blocked"
        active = {x["level"] for x in s["signoffs"] if x["status"] == "active"}
        if "partner" in active and "reviewer" in active:
            return "signed"
        if "reviewer" in active:
            return "reviewed"
        if "preparer" in active:
            return "prepared"
        if s["open_notes"] or s["open_questions"] or s["checks_warning"]:
            return "open_items"
        return "in_progress"

    # ---------------------------------------------------------------- summary vs last year
    SUMMARY_KEYS = [
        ("F1040.1a", "Wages"), ("F1040.2b", "Taxable interest"), ("F1040.3b", "Ordinary dividends"), ("F1040.4b", "Taxable IRA distributions"),
        ("F1040.7", "Capital gain or loss"), ("F1040.8", "Other income (Schedule 1)"), ("F1040.9", "Total income"), ("F1040.10", "Adjustments"),
        ("F1040.11", "Adjusted gross income"), ("F1040.12", "Deductions"), ("F1040.13", "QBI deduction"), ("F1040.15", "Taxable income"),
        ("F1040.16", "Tax"), ("F1040.19", "Child tax credit / other dependents"), ("F1040.23", "Other taxes"), ("F1040.24", "Total tax"),
        ("F1040.25a", "W-2 withholding"), ("F1040.26", "Estimated payments"), ("F1040.33", "Total payments"), ("F1040.34", "Overpaid"), ("F1040.37", "Amount you owe"),
    ]

    def return_summary(self, state: State, vid: str | None = None) -> dict:
        standards = self.standards(state)
        rows = []
        for key, label in self.SUMMARY_KEYS:
            l = self.p.line(key, vid)
            if not l:
                continue
            eff, adj = state.effective_value(key, l["value"])
            rows.append({"key": key, "label": label, "value": eff, "engine_value": l["value"], "adjusted": adj is not None,
                         "variance": self.variance(key, eff, standards)})
        v = self.p.version(vid)
        ca_rows = []
        for key in [k for k in self.p.lines(vid) if k.startswith("F540NR.")]:
            l = self.p.line(key, vid)
            eff, adj = state.effective_value(key, l["value"])
            ca_rows.append({"key": key, "label": l["label"], "value": eff, "engine_value": l["value"], "adjusted": adj is not None, "variance": self.variance(key, eff, standards)})
        return {"version": v["version"], "computed_at": v["computed_at"], "summary": v["summary"], "federal": rows, "california": ca_rows,
                "working_summary": self.working_summary(state, vid)}

    def working_summary(self, state: State, vid: str | None = None) -> dict:
        """Engine summary plus the estimated effect of applied adjustments."""
        v = self.p.version(vid)
        fed = dict(v["summary"]["federal"])
        ca = dict(v["summary"]["california"])
        fed_delta = 0.0
        ca_delta = 0.0
        for adjs in state.applied_adjustments().values():
            for a in adjs:
                te = a.get("tax_effect") or {}
                fed_delta += te.get("federal", 0) or 0
                ca_delta += te.get("california", 0) or 0
        fed["total_tax_working"] = round(fed["total_tax"] + fed_delta)
        fed["balance_due_working"] = round(fed["balance_due"] + fed_delta)
        ca["total_tax_working"] = round(ca["total_tax"] + ca_delta)
        ca["balance_due_working"] = round(ca["balance_due"] + ca_delta)
        return {"federal": fed, "california": ca, "adjustment_effect": {"federal": round(fed_delta), "california": round(ca_delta)}}

    # ---------------------------------------------------------------- documents
    def document_index(self, state: State, vid: str | None = None) -> list[dict]:
        out = []
        v = self.p.version(vid)
        for d in self.p.documents:
            landed = self.p.where_document_landed(d["id"], vid)
            notes = [n for n in state.notes.values() if n["target"] == d["id"]]
            verifs = [x for x in state.verifications if x["target"] == d["id"]]
            out.append({
                "id": d["id"], "title": d["title"], "document_type": d["document_type"], "issuer": d.get("issuer"), "belongs_to": d["belongs_to"],
                "tax_year": d.get("tax_year"), "received_at": d["received_at"], "uploaded_by": d["uploaded_by"], "page_count": d.get("page_count"),
                "marked_corrected": bool(d.get("marked_corrected")), "extraction_status": d["extraction"]["status"],
                "extraction_reason": d["extraction"].get("reason"), "values_total": landed["values_total"], "values_landed": landed["values_landed"],
                "lines": landed["lines"], "used_by_engine": landed["used_by_engine"], "superseded": landed["superseded"], "why_not": landed["why_not"],
                "first_used_in": landed["first_used_in"], "area": self.p.area_of_document(d["id"]), "open_notes": sum(1 for n in notes if n["status"] == "open"),
                "verified": bool(verifs), "received_after_version": d["received_at"] > v["computed_at"],
                "low_confidence_values": sum(1 for e in self.p.evs_by_doc.get(d["id"], []) if e["confidence"] < 0.7),
            })
        return out

    # ---------------------------------------------------------------- version compare
    def compare_versions(self, a: str, b: str) -> dict:
        la, lb = self.p.lines(a), self.p.lines(b)
        rows = []
        for k in sorted(set(la) | set(lb)):
            va = la.get(k, {}).get("value")
            vb = lb.get(k, {}).get("value")
            if va != vb:
                rows.append({"key": k, "label": (lb.get(k) or la.get(k))["label"], "form": (lb.get(k) or la.get(k))["form"], "a": va, "b": vb,
                             "change": "added" if k not in la else ("removed" if k not in lb else "changed"), "area": self.p.area_of_line(k)})
        va_, vb_ = self.p.version(a), self.p.version(b)
        return {"a": a, "b": b, "rows": rows, "summary_a": va_["summary"], "summary_b": vb_["summary"],
                "documents_added": sorted(set(vb_["documents_used"]) - set(va_["documents_used"])),
                "documents_removed": sorted(set(va_["documents_used"]) - set(vb_["documents_used"])),
                "declared_changes": vb_.get("changes_from_previous", [])}

    # ---------------------------------------------------------------- activity
    def activity(self, state: State, since_actor: str | None = None, limit: int = 200) -> list[dict]:
        evs = state.events_since(since_actor) if since_actor else state.events
        out = []
        for e in reversed(evs[-limit:]):
            d = e.to_dict()
            d["undone"] = e.id in state.undone
            d["actor_name"] = (self.p.staff_by_id.get(e.actor) or {}).get("name") or next((c["name"] for c in self.p.firm.get("client_users", []) if c["id"] == e.actor), e.actor)
            out.append(d)
        return out
