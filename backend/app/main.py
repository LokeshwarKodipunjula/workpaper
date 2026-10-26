"""FastAPI application: the workpaper API, live updates over WebSocket, static UI."""
from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import roles
from .checks import run_checks
from .events import EventStore, State
from .packet import AREAS, Packet, load_packet
from .service import Service, tax_effect

app = FastAPI(title="Miraflores Workpaper", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PACKET: Packet = load_packet()
STORE = EventStore()
SVC = Service(PACKET)


# ----------------------------------------------------------------------------- live updates
class Hub:
    def __init__(self) -> None:
        self.clients: dict[WebSocket, dict[str, Any]] = {}

    async def connect(self, ws: WebSocket, actor: str, view: str) -> None:
        await ws.accept()
        self.clients[ws] = {"actor": actor, "view": view}
        await self.broadcast({"type": "presence", "presence": self.presence()})

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.pop(ws, None)

    def presence(self) -> list[dict]:
        out = []
        for info in self.clients.values():
            a = roles.actor(PACKET, info["actor"]) or {"id": info["actor"], "name": info["actor"], "role": "?"}
            out.append({"actor": a["id"], "name": a["name"], "role": a["role"], "view": info["view"]})
        return out

    async def broadcast(self, msg: dict) -> None:
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_text(json.dumps(msg, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


HUB = Hub()


def state() -> State:
    return State(STORE.all())


def current_actor(x_actor: str | None = Header(default=None)) -> dict:
    a = roles.actor(PACKET, x_actor or "")
    if not a:
        raise HTTPException(401, "Pick a role first (X-Actor header).")
    return a


def require(a: dict, cap: str) -> None:
    if not roles.can(a, cap):
        raise HTTPException(403, f"Role '{a['role']}' may not {cap.replace('_', ' ')}.")


def guard_frozen(st: State, a: dict) -> str | None:
    """After acceptance the filed record is frozen; changes go on the amendment layer."""
    if st.is_frozen():
        if st.filing["status"] != "amending":
            raise HTTPException(409, "The filed return is frozen. Open an amendment to change it.")
    return "amendment" if st.filing["status"] == "amending" else None


async def emit(ev, extra: dict | None = None) -> None:
    await HUB.broadcast({"type": "event", "event": ev.to_dict(), **(extra or {})})


SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
ACCOUNT_RE = re.compile(r"\b\d{9,12}\b")          # bank/brokerage account numbers and EINs without the dash
THRESHOLD_RULE_RE = re.compile(r"tax effect over ([\d,]+)")


def partner_threshold(standards: dict) -> int:
    """The firm rule is free text ("...tax effect over 1,000..."); read the number out of it so an
    administrator can change the threshold without a code change. Falls back to 1,000."""
    for rule in standards.get("rules", []):
        m = THRESHOLD_RULE_RE.search(rule)
        if m:
            return int(m.group(1).replace(",", ""))
    return 1000


def mask_if_needed(a: dict, data: Any) -> Any:
    """Mask SSNs, EINs, account numbers and IP PINs for staff without clearance.

    One choke point on the way out, not per route: a new endpoint cannot forget to mask."""
    if a.get("clearance", True):
        return data

    def walk(x):
        if isinstance(x, dict):
            return {k: ("******" if k in ("ip_pin", "ero_pin") and v else walk(v)) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(i) for i in x]
        if isinstance(x, str):
            x = SSN_RE.sub(lambda m: "***-**-" + m.group(0)[-4:], x)
            x = ACCOUNT_RE.sub(lambda m: "****" + m.group(0)[-4:], x)
            return x
        return x
    return walk(data)


# ----------------------------------------------------------------------------- read routes
@app.get("/api/meta")
def meta():
    return {"packet": PACKET.meta, "versions": [{k: v for k, v in ver.items() if k not in ("lines", "assets", "changes_from_previous")} for ver in PACKET.versions],
            "latest_version": PACKET.latest_version_id, "actors": roles.actors(PACKET), "areas": [a.__dict__ for a in AREAS],
            "household": {"filing_status": PACKET.household["filing_status"], "people": [{"id": x["id"], "name": x["name"], "role": x["role"]} for x in PACKET.household["people"]]},
            "firm": {"name": PACKET.firm["name"], "deadlines": PACKET.firm["deadlines"], "budget_hours": PACKET.firm["budget_hours"]}}


@app.get("/api/overview")
def overview(a: dict = Depends(current_actor), version: str | None = None):
    st = state()
    checks = run_checks(PACKET, st, version)
    return {
        "areas": SVC.area_summaries(st, checks, version),
        "summary": SVC.return_summary(st, version),
        "checks": {"fail": sum(1 for c in checks if c["status"] == "fail"), "warn": sum(1 for c in checks if c["status"] == "warn"), "total": len(checks)},
        "open_notes": [n for n in st.notes.values() if n["status"] == "open"],
        "open_questions": [q for q in st.questions.values() if q["status"] == "open"],
        "signoffs": list(st.signoffs.values()),
        "filing": st.filing,
        "since_you_looked": len(st.events_since(a["id"])),
        "deadlines": PACKET.firm["deadlines"],
        "assignments": st.assignments,
        "time": {"by_area": _time_by_area(st), "budget": PACKET.firm["budget_hours"]},
        "client_approvals": st.client_approvals,
        # what the partner must clear before the whole-return sign-off; one list, not a hunt through areas
        "pending_adjustments": [x for x in st.adjustments.values() if x["status"] == "proposed"],
    }


def _time_by_area(st: State) -> dict[str, float]:
    out: dict[str, float] = {}
    for t in st.time_entries:
        out[t["area"]] = out.get(t["area"], 0) + float(t.get("hours", 0))
    return out


@app.get("/api/lines")
def lines(a: dict = Depends(current_actor), area: str | None = None, form: str | None = None, version: str | None = None):
    st = state()
    return mask_if_needed(a, SVC.lines_view(st, version, area, form))


@app.get("/api/lines/{key}")
def line(key: str, a: dict = Depends(current_actor), version: str | None = None):
    st = state()
    lv = SVC.line_view(key, st, version)
    if not lv:
        raise HTTPException(404, "No such line in this version")
    lv["upstream"] = PACKET.upstream(key, version, depth=6)
    lv["downstream"] = [{"key": k, "label": PACKET.line(k, version)["label"], "form": PACKET.line(k, version)["form"], "value": st.effective_value(k, PACKET.line(k, version)["value"])[0]} for k in PACKET.downstream(key, version)]
    lv["sources_resolved"] = [PACKET.resolve_ref(s, version) for s in lv.get("sources") or []]
    lv["rule_text"] = PACKET.engine["rules"].get(lv.get("rule", ""), "")
    lv["history"] = _line_history(key)
    lv["related"] = _related(key, version)
    return mask_if_needed(a, lv)


def _line_history(key: str) -> list[dict]:
    out = []
    prior = SVC.prior_value(key)
    if prior is not None:
        out.append({"version": "2024 return", "value": prior, "computed_at": PACKET.prior_years["return_2024"]["filed"]})
    for v in PACKET.versions:
        l = PACKET.lines(v["version"]).get(key)
        out.append({"version": v["version"], "value": l["value"] if l else None, "computed_at": v["computed_at"], "trigger": v["trigger"]})
    return out


def _related(key: str, version: str | None) -> list[dict]:
    """Links across the return, years and related returns for this line."""
    rel = []
    l = PACKET.line(key, version)
    if not l:
        return rel
    txt = f"{l['label']} {l.get('note', '')}".lower()
    if key.startswith("F7203") or "woodworks" in txt:
        rel.append({"kind": "related_return", "label": "Lindqvist Family Woodworks, Inc. - 2025 Form 1120-S (Willamette CPA Group)", "ref": "py:/basis_records/scorp_lindqvist_family_woodworks"})
    if "ridgeline" in txt or key.startswith("F8582"):
        rel.append({"kind": "related_return", "label": "Ridgeline Real Estate Fund III LP - 2025 Form 1065 and Arizona composite", "ref": "py:/basis_records/partnership_ridgeline"})
    if key.startswith("F8863") or "ada" in txt:
        rel.append({"kind": "related_return", "label": "Ada Lindqvist-Okafor - her own 2025 Form 1040 (claims she can be claimed)", "ref": "household:ada"})
    # california mirror lines
    if l["jurisdiction"] == "federal":
        for k2, l2 in PACKET.lines(version).items():
            if l2["jurisdiction"] == "california" and key in (l2.get("inputs") or []):
                rel.append({"kind": "california", "label": f"{l2['form']} {l2['line']}: {l2['label']}", "ref": k2})
    if SVC.prior_value(key) is not None:
        rel.append({"kind": "prior_year", "label": "Same line on the 2024 return", "ref": f"py:/return_2024/lines/{key}"})
    return rel


@app.get("/api/documents")
def documents(a: dict = Depends(current_actor), version: str | None = None):
    return mask_if_needed(a, SVC.document_index(state(), version))


@app.get("/api/documents/{doc_id}")
def document(doc_id: str, a: dict = Depends(current_actor), version: str | None = None):
    d = PACKET.doc_by_id.get(doc_id)
    if not d:
        raise HTTPException(404)
    st = state()
    landed = PACKET.where_document_landed(doc_id, version)
    log_sensitive_view(a, doc_id)
    out = {"document": d, "landed": landed, "area": PACKET.area_of_document(doc_id),
           "notes": [n for n in st.notes.values() if n["target"] == doc_id],
           "verifications": [v for v in st.verifications if v["target"] == doc_id],
           "attachments": [x for x in st.attachments.values() if x["target"] == doc_id],
           "timeline": [t for t in PACKET.timeline if doc_id in (t.get("refs") or [])],
           "related_documents": [x["id"] for x in PACKET.documents if x["id"] != doc_id and (x["title"].split(" - ")[-1] == d["title"].split(" - ")[-1] or x.get("issuer") and x.get("issuer") == d.get("issuer"))]}
    return mask_if_needed(a, out)


def log_sensitive_view(a: dict, subject: str) -> None:
    """Every unmasked view of a document that carries identifiers is logged (firm rule)."""
    if not a.get("clearance", True):
        return
    d = PACKET.doc_by_id.get(subject)
    if d and any(e["value_type"] in ("ssn", "account_number", "ein") for e in PACKET.evs_by_doc.get(subject, [])):
        STORE.append("view.sensitive", a["id"], a["role"], {"field": "document", "subject": subject}, target=subject, area=PACKET.area_of_document(subject))


@app.get("/api/ref")
def ref(r: str, a: dict = Depends(current_actor), version: str | None = None):
    return mask_if_needed(a, PACKET.resolve_ref(r, version))


@app.get("/api/search")
def search(q: str, a: dict = Depends(current_actor), version: str | None = None):
    st = state()
    hits = PACKET.search(q, version)
    ql = q.lower()
    for n in st.notes.values():
        if ql in n.get("text", "").lower():
            hits.append({"kind": "note", "ref": n["id"], "label": n["text"][:90], "target": n["target"]})
    for qq in st.questions.values():
        if ql in f"{qq.get('text', '')} {qq.get('answer', '')}".lower():
            hits.append({"kind": "question", "ref": qq["id"], "label": qq["text"][:90], "target": qq["target"]})
    return mask_if_needed(a, hits[:60])


@app.get("/api/checks")
def checks(a: dict = Depends(current_actor), version: str | None = None, area: str | None = None):
    res = run_checks(PACKET, state(), version)
    if area:
        res = [c for c in res if c["area"] == area]
    return mask_if_needed(a, res)


@app.get("/api/activity")
def activity(a: dict = Depends(current_actor), since_me: bool = False, limit: int = 200):
    st = state()
    return SVC.activity(st, a["id"] if since_me else None, limit)


@app.get("/api/versions/compare")
def compare(a: str, b: str, actor: dict = Depends(current_actor)):
    if a not in PACKET.version_by_id or b not in PACKET.version_by_id:
        raise HTTPException(404)
    return SVC.compare_versions(a, b)


@app.get("/api/records/{name}")
def records(name: str, a: dict = Depends(current_actor), version: str | None = None):
    """The records a CPA expects, each built from the graph (see records.py)."""
    from . import records as R
    fn = getattr(R, "rec_" + name, None)
    if not fn:
        raise HTTPException(404, f"No record '{name}'")
    return mask_if_needed(a, fn(PACKET, state(), SVC, version))


@app.get("/api/records")
def record_list(a: dict = Depends(current_actor)):
    from . import records as R
    return R.RECORD_LIST


@app.get("/api/household")
def household(a: dict = Depends(current_actor)):
    if a.get("clearance", True) and a["role"] != "client":
        STORE.append("view.sensitive", a["id"], a["role"], {"field": "household", "subject": "household"}, target="household", area="intake_and_engagement")
    return mask_if_needed(a, {"household": PACKET.household, "related_returns": PACKET.household.get("related_returns", [])})


@app.get("/api/firm")
def firm(a: dict = Depends(current_actor)):
    st = state()
    return {"firm": {k: v for k, v in PACKET.firm.items() if k != "firm_identity"}, "standards": SVC.standards(st),
            "overrides": st.standards_overrides, "view_log": st.view_log if roles.can(a, "view_logs") else None,
            "time": {"entries": st.time_entries, "by_area": _time_by_area(st), "budget": PACKET.firm["budget_hours"]},
            "assignments": st.assignments}


@app.get("/api/timeline")
def timeline(a: dict = Depends(current_actor)):
    return {"packet_timeline": PACKET.timeline, "agency": mask_if_needed(a, PACKET.agency), "what_if": PACKET.what_if,
            "planning_2026": PACKET.planning_2026, "post_filing_rates": PACKET.post_filing_rates}


@app.get("/api/client")
def client_view(a: dict = Depends(current_actor)):
    st = state()
    qs = [q for q in st.questions.values() if q.get("to") == "client"]
    return {"questions": qs, "summary": SVC.return_summary(st), "filing": st.filing, "approvals": st.client_approvals,
            "fingerprint": SVC.scope_fingerprint("return", st), "questionnaire": PACKET.client["questionnaire"], "messages": PACKET.client["messages"]}


# ----------------------------------------------------------------------------- write routes
class AdjustIn(BaseModel):
    line_key: str
    new_value: float | int | str
    reason: str
    authority: str | None = None
    category: str | None = None
    evidence: list[str] = []
    batch_id: str | None = None


def _apply_adjustment(a: dict, st: State, body: AdjustIn, layer: str | None, batch_id: str | None) -> Any:
    l = PACKET.line(body.line_key)
    if not l:
        raise HTTPException(404, "No such line")
    old, _ = st.effective_value(body.line_key, l["value"])
    te = tax_effect(PACKET, body.line_key, old, body.new_value, category=body.category)
    threshold = partner_threshold(SVC.standards(st))
    requires_partner = (abs(te["federal"]) > threshold or abs(te["california"]) > threshold) and a["role"] != "partner"
    payload = {"old_value": old, "new_value": body.new_value, "reason": body.reason, "authority": body.authority, "category": te["category"],
               "tax_effect": te, "requires_partner": requires_partner, "status": "proposed" if requires_partner else "applied",
               "evidence": body.evidence, "layer": layer, "engine_value": l["value"]}
    ev = STORE.append("adjustment.proposed", a["id"], a["role"], payload, target=body.line_key, area=PACKET.area_of_line(body.line_key), batch_id=batch_id)
    reopened = []
    if not requires_partner:
        reopened = _reopen_signoffs(a, body.line_key, ev.id, f"{body.line_key} changed from {old} to {body.new_value}")
    return ev, reopened


def _reopen_signoffs(a: dict, line_key: str, cause_event_id: str, cause: str) -> list[dict]:
    st = state()
    area = PACKET.area_of_line(line_key)
    out = []
    for so in st.active_signoffs():
        if so["scope"] in (area, "return"):
            e = STORE.append("signoff.reopened", "system", "system", {"signoff_id": so["id"], "cause": cause, "cause_event_id": cause_event_id}, target=so["scope"], area=so["scope"] if so["scope"] != "return" else None)
            out.append(e.to_dict())
    # client approval is also tied to the amounts presented
    if st.client_approvals and st.client_approvals[-1].get("approved") and st.filing["status"] in ("sent_to_client", "client_approved"):
        STORE.append("filing.status", "system", "system", {"status": "partner_approved", "detail": f"Client approval voided: {cause}. The client must approve the corrected amounts again."}, target="filing")
    return out


@app.post("/api/adjustments")
async def adjust(body: AdjustIn, a: dict = Depends(current_actor)):
    require(a, "adjust")
    st = state()
    layer = guard_frozen(st, a)
    ev, reopened = _apply_adjustment(a, st, body, layer, body.batch_id)
    await emit(ev, {"reopened": reopened})
    return {"event": ev.to_dict(), "reopened": reopened}


class BulkAdjustIn(BaseModel):
    items: list[AdjustIn]


@app.post("/api/adjustments/bulk")
async def adjust_bulk(body: BulkAdjustIn, a: dict = Depends(current_actor)):
    """Act on many items at once; one undo reverses the batch."""
    require(a, "adjust")
    st = state()
    layer = guard_frozen(st, a)
    batch = "batch_" + uuid.uuid4().hex[:10]
    evs = []
    for item in body.items:
        st = state()
        ev, _ = _apply_adjustment(a, st, item, layer, batch)
        evs.append(ev.to_dict())
    await HUB.broadcast({"type": "batch", "batch_id": batch, "count": len(evs), "actor": a["id"]})
    return {"batch_id": batch, "events": evs}


class ApproveIn(BaseModel):
    adjustment_id: str
    approve: bool = True
    reason: str | None = None


@app.post("/api/adjustments/approve")
async def approve(body: ApproveIn, a: dict = Depends(current_actor)):
    require(a, "approve_adjustment")
    st = state()
    adj = st.adjustments.get(body.adjustment_id)
    if not adj:
        raise HTTPException(404)
    if adj["actor"] == a["id"]:
        raise HTTPException(403, "A person may not approve their own adjustment.")
    if body.approve:
        ev = STORE.append("adjustment.approved", a["id"], a["role"], {"adjustment_id": body.adjustment_id}, target=adj["line_key"], area=adj["area"])
        reopened = _reopen_signoffs(a, adj["line_key"], ev.id, f"{adj['line_key']} adjustment approved: {adj['old_value']} -> {adj['new_value']}")
    else:
        ev = STORE.append("adjustment.rejected", a["id"], a["role"], {"adjustment_id": body.adjustment_id, "reason": body.reason}, target=adj["line_key"], area=adj["area"])
        reopened = []
    await emit(ev, {"reopened": reopened})
    return {"event": ev.to_dict(), "reopened": reopened}


class VerifyIn(BaseModel):
    target: str
    type: str
    note: str | None = None
    batch_id: str | None = None


@app.post("/api/verifications")
async def verify(body: VerifyIn, a: dict = Depends(current_actor)):
    require(a, "verify")
    st = state()
    std = SVC.standards(st)
    if body.type not in std["verification_types"]:
        raise HTTPException(400, f"Unknown verification type; firm standards allow {std['verification_types']}")
    area = PACKET.area_of_line(body.target) if PACKET.line(body.target) else (PACKET.area_of_document(PACKET.ev_by_id[body.target]["document_id"]) if body.target in PACKET.ev_by_id else PACKET.area_of_document(body.target))
    ev = STORE.append("verification.recorded", a["id"], a["role"], {"type": body.type, "note": body.note}, target=body.target, area=area, batch_id=body.batch_id)
    await emit(ev)
    return ev.to_dict()


class BulkVerifyIn(BaseModel):
    targets: list[str]
    type: str
    note: str | None = None


@app.post("/api/verifications/bulk")
async def verify_bulk(body: BulkVerifyIn, a: dict = Depends(current_actor)):
    require(a, "verify")
    batch = "batch_" + uuid.uuid4().hex[:10]
    out = []
    for t in body.targets:
        area = PACKET.area_of_line(t) if PACKET.line(t) else (PACKET.area_of_document(PACKET.ev_by_id[t]["document_id"]) if t in PACKET.ev_by_id else PACKET.area_of_document(t))
        out.append(STORE.append("verification.recorded", a["id"], a["role"], {"type": body.type, "note": body.note}, target=t, area=area, batch_id=batch).to_dict())
    await HUB.broadcast({"type": "batch", "batch_id": batch, "count": len(out), "actor": a["id"]})
    return {"batch_id": batch, "events": out}


class NoteIn(BaseModel):
    target: str | None = None
    area: str | None = None
    text: str
    kind: str = "review"          # review | judgment | election | due_diligence | penalty | variance | memo | required_step
    blocking: bool = False
    severity: str = "normal"
    assigned_to: str | None = None
    due: str | None = None
    authority: str | None = None
    step: str | None = None
    alternatives: str | None = None


@app.post("/api/notes")
async def note(body: NoteIn, a: dict = Depends(current_actor)):
    require(a, "note")
    if body.blocking:
        require(a, "block")
    if body.kind == "judgment" and not body.authority:
        raise HTTPException(400, "Firm standard: every judgment call records the authority relied on.")
    area = body.area or (PACKET.area_of_line(body.target) if body.target and PACKET.line(body.target) else (PACKET.area_of_document(body.target) if body.target and body.target in PACKET.doc_by_id else "return_summary"))
    ev = STORE.append("note.created", a["id"], a["role"], body.model_dump(exclude={"target", "area"}), target=body.target, area=area)
    await emit(ev)
    return ev.to_dict()


class NoteActIn(BaseModel):
    note_id: str
    action: str   # resolve | reopen | reply
    text: str | None = None


@app.post("/api/notes/act")
async def note_act(body: NoteActIn, a: dict = Depends(current_actor)):
    require(a, "note")
    st = state()
    n = st.notes.get(body.note_id)
    if not n:
        raise HTTPException(404)
    if body.action == "resolve":
        if n.get("blocking") and n["actor"] != a["id"] and not roles.can(a, "block"):
            raise HTTPException(403, "Only the reviewer who raised it, a reviewer or a partner may resolve a blocking note.")
        ev = STORE.append("note.resolved", a["id"], a["role"], {"note_id": body.note_id, "resolution": body.text}, target=n["target"], area=n["area"])
    elif body.action == "reopen":
        ev = STORE.append("note.reopened", a["id"], a["role"], {"note_id": body.note_id, "reason": body.text}, target=n["target"], area=n["area"])
    else:
        ev = STORE.append("note.replied", a["id"], a["role"], {"note_id": body.note_id, "text": body.text}, target=n["target"], area=n["area"])
    await emit(ev)
    return ev.to_dict()


class QuestionIn(BaseModel):
    to: str          # 'client' or a staff id
    text: str
    target: str | None = None
    area: str | None = None
    due: str | None = None


@app.post("/api/questions")
async def ask(body: QuestionIn, a: dict = Depends(current_actor)):
    require(a, "question_client")
    area = body.area or (PACKET.area_of_line(body.target) if body.target and PACKET.line(body.target) else (PACKET.area_of_document(body.target) if body.target in PACKET.doc_by_id else "return_summary"))
    ev = STORE.append("question.asked", a["id"], a["role"], {"to": body.to, "text": body.text, "due": body.due}, target=body.target, area=area)
    await emit(ev)
    return ev.to_dict()


class AnswerIn(BaseModel):
    question_id: str
    answer: str


@app.post("/api/questions/answer")
async def answer(body: AnswerIn, a: dict = Depends(current_actor)):
    st = state()
    q = st.questions.get(body.question_id)
    if not q:
        raise HTTPException(404)
    if q["to"] == "client":
        if a["role"] != "client":
            raise HTTPException(403, "Only the client answers client questions.")
    elif q["to"] != a["id"] and a["role"] not in ("partner", "reviewer"):
        raise HTTPException(403, "This question was addressed to someone else.")
    ev = STORE.append("question.answered", a["id"], a["role"], {"question_id": body.question_id, "answer": body.answer}, target=q["target"], area=q["area"])
    await emit(ev)
    return ev.to_dict()


@app.post("/api/attachments")
async def attach(target: str = Form(...), description: str = Form(""), file: UploadFile = File(...), a: dict = Depends(current_actor)):
    require(a, "attach")
    data = await file.read()
    if len(data) > 15_000_000:
        raise HTTPException(413, "15 MB limit")
    key = STORE.put_blob(file.filename or "file", file.content_type or "application/octet-stream", data)
    area = PACKET.area_of_line(target) if PACKET.line(target) else (PACKET.area_of_document(target) if target in PACKET.doc_by_id else "return_summary")
    ev = STORE.append("attachment.added", a["id"], a["role"], {"name": file.filename, "mime": file.content_type, "size": len(data), "description": description, "storage_key": key}, target=target, area=area)
    await emit(ev)
    return ev.to_dict()


@app.get("/api/attachments/{key}")
def get_attachment(key: str, a: dict = Depends(current_actor)):
    b = STORE.get_blob(key)
    if not b:
        raise HTTPException(404)
    return Response(content=b.data, media_type=b.mime or "application/octet-stream", headers={"Content-Disposition": f'inline; filename="{b.name}"'})


class SignoffIn(BaseModel):
    scope: str     # area id or 'return'
    level: str     # preparer | reviewer | partner


@app.post("/api/signoffs")
async def signoff(body: SignoffIn, a: dict = Depends(current_actor)):
    require(a, f"signoff_{body.level}")
    st = state()
    # a person may not review or sign off on work they prepared
    if body.level in ("reviewer", "partner"):
        prepared_by = {adj["actor"] for adj in st.adjustments.values() if adj["status"] == "applied" and (body.scope == "return" or adj["area"] == body.scope)}
        prepared_by |= {s["actor"] for s in st.signoffs.values() if s["level"] == "preparer" and s["scope"] == body.scope}
        if a["id"] in prepared_by:
            raise HTTPException(403, "Firm standard: a person may not review or sign off on work they prepared.")
    if body.scope == "return":
        blocking = st.open_blocking_notes()
        if blocking and body.level == "partner":
            raise HTTPException(409, f"{len(blocking)} open review note(s) block the return.")
        pending = [x for x in st.adjustments.values() if x["status"] == "proposed"]
        if pending and body.level == "partner":
            raise HTTPException(409, f"{len(pending)} adjustment(s) await partner approval.")
    fp = SVC.scope_fingerprint(body.scope, st)
    ev = STORE.append("signoff.given", a["id"], a["role"], {"scope": body.scope, "level": body.level, "fingerprint": fp}, target=body.scope, area=body.scope if body.scope != "return" else None)
    await emit(ev)
    return ev.to_dict()


class AssignIn(BaseModel):
    area: str
    assignee: str
    due: str | None = None


@app.post("/api/assignments")
async def assign(body: AssignIn, a: dict = Depends(current_actor)):
    require(a, "assign")
    ev = STORE.append("assignment.set", a["id"], a["role"], body.model_dump(), target=body.area, area=body.area)
    await emit(ev)
    return ev.to_dict()


class TimeIn(BaseModel):
    area: str
    hours: float
    note: str | None = None


@app.post("/api/time")
async def log_time(body: TimeIn, a: dict = Depends(current_actor)):
    require(a, "time")
    ev = STORE.append("time.logged", a["id"], a["role"], body.model_dump(), target=body.area, area=body.area)
    await emit(ev)
    return ev.to_dict()


class StandardIn(BaseModel):
    path: str
    value: Any


@app.post("/api/standards")
async def standards(body: StandardIn, a: dict = Depends(current_actor)):
    require(a, "standards")
    ev = STORE.append("standards.updated", a["id"], a["role"], body.model_dump(), target=body.path)
    await emit(ev)
    return ev.to_dict()


class FilingIn(BaseModel):
    status: str
    detail: str | None = None


FILING_FLOW = ["open", "in_review", "partner_approved", "sent_to_client", "client_approved", "extension_filed", "efiled", "rejected", "accepted", "amending", "amended_filed"]


@app.post("/api/filing")
async def filing(body: FilingIn, a: dict = Depends(current_actor)):
    require(a, "filing")
    st = state()
    if body.status not in FILING_FLOW:
        raise HTTPException(400, f"status must be one of {FILING_FLOW}")
    if body.status == "sent_to_client":
        if not any(x["level"] == "partner" and x["scope"] == "return" for x in st.active_signoffs()):
            raise HTTPException(409, "Partner sign-off on the return is required before it goes to the client.")
        if st.open_blocking_notes():
            raise HTTPException(409, "Open review notes block filing.")
    if body.status == "efiled":
        if not any(x.get("approved") for x in st.client_approvals) or st.filing["status"] != "client_approved":
            raise HTTPException(409, "Client approval and e-file authorization (Form 8879) are required first.")
        if st.open_blocking_notes():
            raise HTTPException(409, "Open review notes block filing.")
        fp_now = SVC.scope_fingerprint("return", st)
        if st.client_approvals[-1].get("fingerprint") != fp_now:
            raise HTTPException(409, "The return changed after the client signed. Send it to the client again.")
    ev = STORE.append("filing.status", a["id"], a["role"], {"status": body.status, "detail": body.detail, "fingerprint": SVC.scope_fingerprint("return", st)}, target="filing")
    await emit(ev)
    return ev.to_dict()


class ClientApprovalIn(BaseModel):
    approved: bool
    pin: str | None = None
    comment: str | None = None


@app.post("/api/client/approve")
async def client_approve(body: ClientApprovalIn, a: dict = Depends(current_actor)):
    require(a, "client_approve")
    st = state()
    if st.filing["status"] not in ("sent_to_client",):
        raise HTTPException(409, "Nothing is awaiting your approval.")
    fp = SVC.scope_fingerprint("return", st)
    ws = SVC.working_summary(st)
    ev = STORE.append("client.approval", a["id"], a["role"], {"approved": body.approved, "pin": body.pin, "comment": body.comment, "fingerprint": fp,
                                                             "amounts": {"federal_balance_due": ws["federal"]["balance_due_working"], "california_balance_due": ws["california"]["balance_due_working"]}}, target="filing")
    if body.approved:
        STORE.append("filing.status", a["id"], a["role"], {"status": "client_approved", "detail": "Form 8879 / FTB 8879 signed electronically.", "fingerprint": fp}, target="filing")
    await emit(ev)
    return ev.to_dict()


@app.post("/api/read-marker")
async def read_marker(a: dict = Depends(current_actor)):
    ev = STORE.append("read.marker", a["id"], a["role"], {})
    return ev.to_dict()


class OverrideIn(BaseModel):
    check_id: str
    status: str   # accepted | waived
    reason: str


@app.post("/api/checks/override")
async def check_override(body: OverrideIn, a: dict = Depends(current_actor)):
    require(a, "check_override")
    ev = STORE.append("check.override", a["id"], a["role"], body.model_dump(), target=body.check_id)
    await emit(ev)
    return ev.to_dict()


class WhatIfIn(BaseModel):
    name: str
    adjustments: list[dict]   # [{line_key, new_value, category?}]


@app.post("/api/whatif")
async def whatif(body: WhatIfIn, a: dict = Depends(current_actor), save: bool = False):
    """Estimate the effect of hypothetical changes without touching the return."""
    require(a, "whatif")
    st = state()
    rows = []
    fed = ca = 0.0
    for item in body.adjustments:
        l = PACKET.line(item["line_key"])
        if not l:
            continue
        old, _ = st.effective_value(item["line_key"], l["value"])
        te = tax_effect(PACKET, item["line_key"], old, item["new_value"], category=item.get("category"))
        fed += te["federal"]
        ca += te["california"]
        rows.append({"line_key": item["line_key"], "label": l["label"], "old": old, "new": item["new_value"], "effect": te})
    ws = SVC.working_summary(st)
    result = {"name": body.name, "rows": rows, "federal_tax_change": round(fed), "california_tax_change": round(ca),
              "federal_balance_after": round(ws["federal"]["balance_due_working"] + fed), "california_balance_after": round(ws["california"]["balance_due_working"] + ca),
              "engine_alternatives": PACKET.what_if["alternatives"]}
    if save:
        ev = STORE.append("whatif.saved", a["id"], a["role"], {"name": body.name, "adjustments": body.adjustments, "result": {k: v for k, v in result.items() if k != "engine_alternatives"}})
        result["event"] = ev.to_dict()
    return result


class UndoIn(BaseModel):
    event_id: str | None = None
    batch_id: str | None = None


@app.post("/api/undo")
async def undo(body: UndoIn, a: dict = Depends(current_actor)):
    require(a, "undo")
    if not body.event_id and not body.batch_id:
        raise HTTPException(400)
    if body.event_id:
        target = STORE.get(body.event_id)
        if not target:
            raise HTTPException(404)
        if target.actor != a["id"] and a["role"] not in ("partner", "firm_administrator"):
            raise HTTPException(403, "You can only undo your own actions.")
    ev = STORE.append("undo", a["id"], a["role"], {"undone_event_id": body.event_id, "batch_id": body.batch_id})
    await emit(ev)
    return ev.to_dict()


class CarryIn(BaseModel):
    item: str
    value: Any
    note: str | None = None


@app.post("/api/carryforward")
async def carry(body: CarryIn, a: dict = Depends(current_actor)):
    require(a, "carryforward")
    ev = STORE.append("carryforward.noted", a["id"], a["role"], body.model_dump(), target=body.item)
    await emit(ev)
    return ev.to_dict()


@app.post("/api/admin/reset")
async def reset(a: dict = Depends(current_actor)):
    require(a, "standards")
    STORE.reset()
    await HUB.broadcast({"type": "reset"})
    return {"ok": True}


@app.post("/api/admin/seed")
async def seed(a: dict = Depends(current_actor)):
    """Replay the season: seed the event log with the actions a firm would have taken, for the demo."""
    require(a, "standards")
    from .seed import seed_events
    n = seed_events(PACKET, STORE, SVC)
    await HUB.broadcast({"type": "reset"})
    return {"seeded": n}


# ----------------------------------------------------------------------------- websocket
@app.get("/api/heartbeat")
def heartbeat():
    """For hosts without WebSockets (serverless): the UI polls this and refetches when the sequence moves."""
    return {"seq": STORE.last_seq(), "live": "websocket" if HUB.clients else "polling"}


@app.websocket("/ws")
async def ws(websocket: WebSocket, actor: str = "anon", view: str = ""):
    await HUB.connect(websocket, actor, view)
    try:
        while True:
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
                if data.get("type") == "view":
                    HUB.clients[websocket]["view"] = data.get("view", "")
                    await HUB.broadcast({"type": "presence", "presence": HUB.presence()})
            except Exception:
                pass
    except WebSocketDisconnect:
        HUB.disconnect(websocket)
        await HUB.broadcast({"type": "presence", "presence": HUB.presence()})


# ----------------------------------------------------------------------------- static UI
DIST = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    def dist_file(full_path: str) -> str | None:
        """Resolve a request path to a file inside the built UI, or None. Anything that escapes
        the dist directory (../, absolute paths) is treated as a client route."""
        candidate = os.path.realpath(os.path.join(DIST, full_path))
        inside = candidate == DIST or candidate.startswith(DIST + os.sep)
        return candidate if full_path and inside and os.path.isfile(candidate) else None

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        return FileResponse(dist_file(full_path) or os.path.join(DIST, "index.html"))
