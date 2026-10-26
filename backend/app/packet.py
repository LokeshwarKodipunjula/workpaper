"""Immutable packet model.

The packet is pipeline output and never changes. Everything the workpaper adds
lives in the event log (see events.py). This module loads the JSON once and
builds the indices the provenance graph needs:

  document -> pages -> extracted values -> return lines -> dependent lines
  line -> inputs (other lines) / sources (any reference string)

Reference strings follow the README formats (ev-NNNN, D01..D74, qa-NN, msg-NN,
call-NN, py:/pointer, agency:/pointer, asset:<id>, household:<id>,
ref:param.<name>, ref:fx.SEK.<rate>, timeline:<id>, doc:<id>#page<n>, and
line keys such as F1040.11). resolve_ref() turns any of them into a typed node.
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable

LINE_KEY_RE = re.compile(r"^(F\d{4}[A-Z]?(?:-[CE])?|Sch[A-Z0-9]+|SchCA540NR|ScheduleS|FTB\d+[A-Z]?)\.(.+)$")


def json_pointer(doc: Any, pointer: str) -> Any:
    """RFC 6901 pointer lookup. Returns None if the path does not exist."""
    if pointer in ("", "/"):
        return doc
    cur = doc
    for raw in pointer.lstrip("/").split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        else:
            return None
    return cur


@dataclass
class Area:
    id: str
    title: str
    forms: list[str] = field(default_factory=list)
    key_prefixes: list[str] = field(default_factory=list)
    document_ids: list[str] = field(default_factory=list)
    budget_hours: float | None = None
    description: str = ""


# Area taxonomy. Lines map by form / key prefix, documents by explicit id.
# The ids match firm.budget_hours where one exists so time can be tracked against budget.
AREAS: list[Area] = [
    Area("intake_and_engagement", "Intake, identity & engagement",
         document_ids=["D01", "D02", "D03", "D04", "D05", "D06", "D07", "D70", "D71"],
         description="Engagement letter, consents, identity, household, prior return on file."),
    Area("wages_and_stock_compensation", "Wages & stock compensation",
         forms=["F6251", "F8959"], key_prefixes=["F1040.1", "Sch2.1", "Sch3.11"],
         document_ids=["D08", "D09", "D10", "D11", "D12", "D13", "D73"],
         description="Two W-2s, RSU/ESPP/ISO, AMT from the ISO exercise, Medicare and Social Security wages."),
    Area("investments_and_digital_assets", "Investments & digital assets",
         forms=["SchB", "SchD", "F8949", "F8960", "F8938"],
         document_ids=["D28", "D29", "D30", "D31", "D32", "D33", "D34", "D35", "D36", "D74"],
         description="Interest, dividends, three brokerages, crypto, the Swedish account."),
    Area("business", "Business: Lindqvist Studio",
         forms=["SchC", "SchSE", "F4562-C", "F8995", "F8995A"], key_prefixes=["Sch1.15", "Sch1.16", "Sch1.17", "Sch1.3", "F1040.13"],
         document_ids=["D14", "D15", "D16", "D17", "D18", "D19", "D20", "D21", "D22", "D23", "D24", "D25", "D26", "D27"],
         description="Schedule C from the books, home office, vehicle, equipment, SE tax, SEP, SE health insurance, QBI."),
    Area("rentals_and_sale", "Rentals & the condo sale",
         forms=["SchE", "F4797", "F4562-E", "F8582", "FTB3885A"],
         document_ids=["D46", "D47", "D48", "D49", "D50", "D51", "D52", "D53"],
         description="1450 Fremont Way (Sacramento) and the Austin condo sold 10/15/2025; depreciation and passive losses."),
    Area("pass_throughs_and_basis", "Pass-throughs & basis",
         forms=["F7203"], key_prefixes=["SchE.28", "SchE.29", "SchE.30", "SchE.31", "SchE.32"],
         document_ids=["D37", "D38", "D39", "D40"],
         description="Woodworks S corporation (basis gaps) and the late Ridgeline K-1."),
    Area("retirement_and_hsa", "Retirement & HSA",
         forms=["F8606", "F8889"], key_prefixes=["F1040.4", "Sch1.13", "Sch1.20"],
         document_ids=["D41", "D42", "D43", "D44", "D45"],
         description="Backdoor Roth (Form 8606), HSA (Form 8889)."),
    Area("deductions_and_credits", "Deductions & credits",
         forms=["SchA", "F8283", "F8812", "F8863", "F2441", "F8867"], key_prefixes=["F1040.12", "F1040.14", "F1040.19", "Sch3.1", "Sch3.2", "Sch3.3", "Sch3.4", "Sch3.5", "Sch3.6", "Sch3.7", "Sch3.8"],
         document_ids=["D54", "D55", "D56", "D57", "D58", "D59", "D60", "D61", "D62", "D63", "D64", "D65", "D66"],
         description="Itemized deductions, charitable gifts (cash, stock, car), education, dependent care, child credits, due diligence."),
    Area("payments_and_penalties", "Payments, penalties & filing",
         forms=["F2210", "FTB5805"], key_prefixes=["F1040.2", "F1040.3", "F540NR.8", "F540NR.9", "F540NR.1"],
         document_ids=["D67", "D68", "D69", "D72"],
         description="Withholding, estimates, extension payment, underpayment penalty, IRS and FTB records, e-file."),
    Area("california", "California part-year",
         forms=["SchCA540NR", "F540NR", "ScheduleS"],
         document_ids=[],
         description="Residency split, Schedule CA (540NR), Schedule S, California-source income."),
    Area("return_summary", "Return summary & tax computation",
         forms=["F1040", "Sch1", "Sch2", "Sch3"],
         document_ids=[],
         description="Form 1040 and its schedules: everything that is not claimed by a more specific area."),
]
AREA_BY_ID = {a.id: a for a in AREAS}


class Packet:
    def __init__(self, raw: dict[str, Any]):
        self.raw = raw
        self.meta = raw["packet"]
        self.readme = raw["readme"]
        self.household = raw["household"]
        self.documents: list[dict] = raw["documents"]
        self.extracted_values: list[dict] = raw["extracted_values"]
        self.client = raw["client"]
        self.firm = raw["firm"]
        self.prior_years = raw["prior_years"]
        self.agency = raw["tax_agency_records"]
        self.timeline: list[dict] = raw["timeline"]
        self.engine = raw["engine_reference"]
        self.versions: list[dict] = raw["return_versions"]
        self.what_if = raw["what_if"]
        self.planning_2026 = raw["planning_reference_2026"]
        self.post_filing_rates = raw["post_filing_rates"]
        self.fx_rates = raw["fx_rates"]
        self._index()

    # ------------------------------------------------------------------ indices
    def _index(self) -> None:
        self.doc_by_id = {d["id"]: d for d in self.documents}
        self.ev_by_id = {e["id"]: e for e in self.extracted_values}
        self.evs_by_doc: dict[str, list[dict]] = defaultdict(list)
        for e in self.extracted_values:
            self.evs_by_doc[e["document_id"]].append(e)
        self.version_by_id = {v["version"]: v for v in self.versions}
        self.latest_version_id = self.versions[-1]["version"]
        # line indices per version
        self.lines_by_version: dict[str, dict[str, dict]] = {}
        self.dependents_by_version: dict[str, dict[str, list[str]]] = {}
        self.lines_by_ev: dict[str, dict[str, list[str]]] = {}
        self.lines_by_doc: dict[str, dict[str, set[str]]] = {}
        for v in self.versions:
            vid = v["version"]
            lines = {l["key"]: l for l in v["lines"]}
            self.lines_by_version[vid] = lines
            deps: dict[str, list[str]] = defaultdict(list)
            by_ev: dict[str, list[str]] = defaultdict(list)
            by_doc: dict[str, set[str]] = defaultdict(set)
            for l in v["lines"]:
                for inp in l.get("inputs") or []:
                    deps[inp].append(l["key"])
                for s in l.get("sources") or []:
                    if s.startswith("ev-"):
                        by_ev[s].append(l["key"])
                        ev = self.ev_by_id.get(s)
                        if ev:
                            by_doc[ev["document_id"]].add(l["key"])
                    elif s.startswith("doc:"):
                        by_doc[s[4:].split("#")[0]].add(l["key"])
                    elif re.match(r"^D\d\d$", s):
                        by_doc[s].add(l["key"])
            self.dependents_by_version[vid] = deps
            self.lines_by_ev[vid] = by_ev
            self.lines_by_doc[vid] = by_doc
        self.qa_by_id = {q["id"]: q for q in self.client.get("questionnaire", [])}
        self.msg_by_id = {m["id"]: m for m in self.client.get("messages", [])}
        self.call_by_id = {c["id"]: c for c in self.client.get("call_notes", [])}
        self.staff_by_id = {s["id"]: s for s in self.firm["staff"]}
        self.timeline_by_id = {t["id"]: t for t in self.timeline}
        self.people_by_id = {p["id"]: p for p in self.household["people"]}
        self.prior_asset_by_id = {a["asset_id"]: a for a in self.prior_years.get("asset_records", [])}
        # area index
        self.area_of_doc: dict[str, str] = {}
        for a in AREAS:
            for d in a.document_ids:
                self.area_of_doc[d] = a.id
        for a in AREAS:
            a.budget_hours = self.firm.get("budget_hours", {}).get(a.id)
        self._area_of_line_cache: dict[str, str] = {}

    # ------------------------------------------------------------------ areas
    def area_of_line(self, key: str) -> str:
        if key in self._area_of_line_cache:
            return self._area_of_line_cache[key]
        m = LINE_KEY_RE.match(key)
        form = m.group(1) if m else key.split(".")[0]
        result = "return_summary"
        # key prefixes win over form membership (e.g. F1040.1a -> wages)
        for a in AREAS:
            if any(key.startswith(p) for p in a.key_prefixes):
                result = a.id
                break
        else:
            for a in AREAS:
                if form in a.forms:
                    result = a.id
                    break
        self._area_of_line_cache[key] = result
        return result

    def area_of_document(self, doc_id: str) -> str:
        return self.area_of_doc.get(doc_id, "intake_and_engagement")

    # ------------------------------------------------------------------ lookups
    def version(self, vid: str | None = None) -> dict:
        return self.version_by_id[vid or self.latest_version_id]

    def line(self, key: str, vid: str | None = None) -> dict | None:
        return self.lines_by_version[vid or self.latest_version_id].get(key)

    def lines(self, vid: str | None = None) -> dict[str, dict]:
        return self.lines_by_version[vid or self.latest_version_id]

    def dependents(self, key: str, vid: str | None = None) -> list[str]:
        return self.dependents_by_version[vid or self.latest_version_id].get(key, [])

    def page(self, doc_id: str, page_no: int) -> dict | None:
        doc = self.doc_by_id.get(doc_id)
        if not doc:
            return None
        for p in doc.get("pages", []):
            if p["page"] == page_no:
                return p
        return None

    def lines_citing_ev(self, ev_id: str, vid: str | None = None) -> list[str]:
        return self.lines_by_ev[vid or self.latest_version_id].get(ev_id, [])

    def lines_citing_doc(self, doc_id: str, vid: str | None = None) -> list[str]:
        return sorted(self.lines_by_doc[vid or self.latest_version_id].get(doc_id, set()))

    def first_version_using(self, doc_id: str) -> str | None:
        for v in self.versions:
            if doc_id in v.get("documents_used", []):
                return v["version"]
        return None

    # ------------------------------------------------------------------ lineage
    def upstream(self, key: str, vid: str | None = None, depth: int = 12) -> dict:
        """Full build tree for a line: inputs recursively plus leaf sources."""
        vid = vid or self.latest_version_id
        seen: set[str] = set()

        def walk(k: str, d: int) -> dict:
            l = self.line(k, vid)
            node = {"key": k, "line": l, "inputs": [], "sources": []}
            if not l or d <= 0 or k in seen:
                return node
            seen.add(k)
            node["inputs"] = [walk(i, d - 1) for i in l.get("inputs") or []]
            node["sources"] = [self.resolve_ref(s, vid) for s in l.get("sources") or []]
            return node

        return walk(key, depth)

    def downstream(self, key: str, vid: str | None = None, depth: int = 12) -> list[str]:
        """Every line that (transitively) depends on this one, in BFS order."""
        vid = vid or self.latest_version_id
        out: list[str] = []
        frontier = [key]
        seen = {key}
        while frontier and depth > 0:
            nxt: list[str] = []
            for k in frontier:
                for d in self.dependents(k, vid):
                    if d not in seen:
                        seen.add(d)
                        out.append(d)
                        nxt.append(d)
            frontier = nxt
            depth -= 1
        return out

    def where_document_landed(self, doc_id: str, vid: str | None = None) -> dict:
        """For a document: every extracted value, where each landed (lines), and why not if nowhere."""
        vid = vid or self.latest_version_id
        v = self.version(vid)
        doc = self.doc_by_id[doc_id]
        used = doc_id in v.get("documents_used", [])
        superseded = doc_id in v.get("documents_superseded", [])
        values = []
        for e in self.evs_by_doc.get(doc_id, []):
            values.append({"ev": e, "lines": self.lines_citing_ev(e["id"], vid)})
        n_landed = sum(1 for x in values if x["lines"])
        reason = None
        status = doc["extraction"]["status"]
        if superseded:
            reason = "Superseded by a corrected document."
        elif status == "not_extracted":
            reason = doc["extraction"].get("reason") or "Not extracted."
        elif not used:
            reason = "Received after this version was computed; not in documents_used." if doc["received_at"] > v["computed_at"] else "In file but not used by the engine for this version."
        elif n_landed == 0:
            reason = "Used as reference only: no line cites a value from it."
        return {
            "document_id": doc_id,
            "version": vid,
            "used_by_engine": used,
            "superseded": superseded,
            "first_used_in": self.first_version_using(doc_id),
            "values": values,
            "values_total": len(values),
            "values_landed": n_landed,
            "lines": self.lines_citing_doc(doc_id, vid),
            "why_not": reason,
        }

    # ------------------------------------------------------------------ refs
    def resolve_ref(self, ref: str, vid: str | None = None) -> dict:
        """Turn any README reference string into a typed node with a human label."""
        vid = vid or self.latest_version_id
        node: dict[str, Any] = {"ref": ref, "kind": "unknown", "label": ref, "data": None}
        try:
            if ref.startswith("ev-"):
                ev = self.ev_by_id.get(ref)
                if ev:
                    doc = self.doc_by_id.get(ev["document_id"], {})
                    node.update(kind="extracted_value", data=ev,
                                label=f"{doc.get('title', ev['document_id'])} - {ev['label']}",
                                document_id=ev["document_id"], page=ev["page"], value=ev["value"],
                                confidence=ev["confidence"], area=self.area_of_document(ev["document_id"]))
            elif re.match(r"^D\d\d$", ref):
                doc = self.doc_by_id.get(ref)
                if doc:
                    node.update(kind="document", data={k: v for k, v in doc.items() if k != "pages"},
                                label=doc["title"], document_id=ref, area=self.area_of_document(ref))
            elif ref.startswith("doc:"):
                m = re.match(r"^doc:(D\d\d)#page(\d+)$", ref)
                if m:
                    doc = self.doc_by_id.get(m.group(1))
                    node.update(kind="document_page", document_id=m.group(1), page=int(m.group(2)),
                                label=f"{doc['title'] if doc else m.group(1)} - page {m.group(2)} (not extracted)",
                                data=self.page(m.group(1), int(m.group(2))))
            elif ref.startswith("qa-"):
                q = self.qa_by_id.get(ref)
                if q:
                    node.update(kind="client_answer", data=q, label=f"Client answer: {q['question'][:80]}")
            elif ref.startswith("msg-"):
                m_ = self.msg_by_id.get(ref)
                if m_:
                    node.update(kind="client_message", data=m_, label=f"Message from {m_['from']} {m_['sent_at'][:10]}")
            elif ref.startswith("call-"):
                c = self.call_by_id.get(ref)
                if c:
                    node.update(kind="call_note", data=c, label=f"Call notes {c['date'][:10]}")
            elif ref.startswith("py:/"):
                val = json_pointer(self.prior_years, ref[3:])
                node.update(kind="prior_year", data=val, label=f"Prior years: {ref[4:]}")
            elif ref.startswith("agency:/"):
                val = json_pointer(self.agency, ref[7:])
                node.update(kind="agency_record", data=val, label=f"Agency record: {ref[8:]}")
            elif ref.startswith("asset:"):
                aid = ref[6:]
                cur = next((a for a in self.version(vid).get("assets", []) if a["asset_id"] == aid), None)
                prior = self.prior_asset_by_id.get(aid)
                node.update(kind="asset", data={"current": cur, "prior": prior}, label=f"Asset {aid}: {(cur or prior or {}).get('description', '')}")
            elif ref.startswith("household:"):
                p = self.people_by_id.get(ref[10:])
                if p:
                    node.update(kind="person", data=p, label=p["name"])
            elif ref.startswith("ref:param."):
                name = ref[len("ref:param."):]
                node.update(kind="engine_parameter", data=json_pointer(self.engine["parameters"], "/" + name.replace(".", "/")), label=f"Engine parameter {name}")
            elif ref.startswith("ref:fx."):
                parts = ref.split(".")
                node.update(kind="fx_rate", data=json_pointer(self.engine["parameters"], "/fx/" + "/".join(parts[1:])), label=f"FX rate {'.'.join(parts[1:])}")
            elif ref.startswith("timeline:"):
                t = self.timeline_by_id.get(ref[9:])
                if t:
                    node.update(kind="timeline_event", data=t, label=f"{t['event']} {t['at'][:10]}")
            elif ref.startswith("v") and ref in self.version_by_id:
                node.update(kind="return_version", data={k: v for k, v in self.version_by_id[ref].items() if k != "lines"}, label=f"Return version {ref}")
            elif LINE_KEY_RE.match(ref):
                l = self.line(ref, vid)
                if l:
                    node.update(kind="line", data=l, label=f"{l['form']} line {l['line']}: {l['label']}", value=l["value"], area=self.area_of_line(ref))
                else:
                    node.update(kind="line", label=f"Line {ref} (not in {vid})")
        except Exception as exc:  # pragma: no cover - defensive
            node["error"] = str(exc)
        return node

    # ------------------------------------------------------------------ search
    def search(self, q: str, vid: str | None = None, limit: int = 40) -> list[dict]:
        ql = q.strip().lower()
        if not ql:
            return []
        out: list[dict] = []
        num = None
        try:
            num = float(ql.replace(",", "").replace("$", ""))
        except ValueError:
            pass
        for l in self.lines(vid).values():
            hay = f"{l['key']} {l['label']} {l.get('note', '')}".lower()
            if ql in hay or (num is not None and isinstance(l["value"], (int, float)) and abs(float(l["value"]) - num) < 0.5):
                out.append({"kind": "line", "ref": l["key"], "label": f"{l['form']} {l['line']} - {l['label']}", "value": l["value"], "area": self.area_of_line(l["key"])})
        for d in self.documents:
            hay = f"{d['id']} {d['title']} {d['document_type']} {d['issuer'] if 'issuer' in d else ''} {d.get('file_name', '')}".lower()
            if ql in hay:
                out.append({"kind": "document", "ref": d["id"], "label": d["title"], "area": self.area_of_document(d["id"])})
        for e in self.extracted_values:
            hay = f"{e['id']} {e['label']} {e['field']} {e['text_as_read']}".lower()
            if ql in hay or (num is not None and isinstance(e["value"], (int, float)) and abs(float(e["value"]) - num) < 0.5):
                out.append({"kind": "extracted_value", "ref": e["id"], "label": f"{e['label']} ({e['document_id']} p{e['page']})", "value": e["value"], "area": self.area_of_document(e["document_id"])})
                if len(out) > limit * 3:
                    break
        for qa in self.client.get("questionnaire", []):
            if ql in f"{qa['question']} {qa['answer']}".lower():
                out.append({"kind": "client_answer", "ref": qa["id"], "label": qa["question"][:90]})
        for m in self.client.get("messages", []):
            if ql in m["text"].lower():
                out.append({"kind": "client_message", "ref": m["id"], "label": m["text"][:90]})
        return out[:limit]


_PACKET: Packet | None = None


def packet_path() -> str:
    env = os.environ.get("PACKET_PATH")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "data", "okafor_lindqvist_2025_packet.json"))


def load_packet(path: str | None = None) -> Packet:
    global _PACKET
    if _PACKET is None or path:
        with open(path or packet_path(), encoding="utf-8") as f:
            _PACKET = Packet(json.load(f))
    return _PACKET
