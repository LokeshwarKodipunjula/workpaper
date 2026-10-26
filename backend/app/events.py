"""Append-only event log and its projection (the workpaper state).

Nothing in the workpaper is ever updated in place. Every action appends an
Event; the State is rebuilt by folding events in sequence. Undo appends a
compensating event (undo_of = original id). Bulk actions share a batch_id so
one undo reverses the whole batch.

Event types (payload shape in parentheses):
  adjustment.proposed   (line_key, old_value, new_value, reason, authority, category,
                         tax_effect{federal,california}, requires_partner, status)
  adjustment.approved   (adjustment_id)            partner approves a >1,000 adjustment
  adjustment.rejected   (adjustment_id, reason)
  verification.recorded (target, type, note)      target: line key or ev id
  note.created          (text, blocking, severity, assigned_to, due, kind)  kind: review|judgment|election|due_diligence|penalty|memo
  note.resolved         (note_id, resolution)
  note.reopened         (note_id, reason)
  question.asked        (to, text)                 to: 'client' or staff id
  question.answered     (question_id, answer)
  attachment.added      (name, mime, size, description, storage_key)
  signoff.given         (scope, level, fingerprint)   scope: area id or 'return'
  signoff.reopened      (signoff_id, cause)
  signoff.withdrawn     (signoff_id)
  assignment.set        (area, assignee, due)
  time.logged           (area, hours, note)
  view.sensitive        (field, subject)
  standards.updated     (path, value)
  filing.status         (status, detail)
  client.approval       (approved, pin, fingerprint)
  read.marker           ()                          per-user "last looked" marker
  check.override        (check_id, status, reason)   status: accepted|waived
  whatif.saved          (name, adjustments[])
  carryforward.noted    (item, value, note)
  undo                  (undone_event_id or batch_id)
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import Column, Integer, LargeBinary, String, Text, create_engine, select, func
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class EventRow(Base):
    __tablename__ = "events"
    seq = Column(Integer, primary_key=True, autoincrement=True)
    id = Column(String(40), unique=True, nullable=False)
    at = Column(String(40), nullable=False)
    actor = Column(String(40), nullable=False)
    role = Column(String(40), nullable=False)
    type = Column(String(60), nullable=False, index=True)
    target = Column(String(200), nullable=True, index=True)
    area = Column(String(60), nullable=True, index=True)
    batch_id = Column(String(40), nullable=True, index=True)
    undo_of = Column(String(40), nullable=True)
    payload = Column(Text, nullable=False)


class BlobRow(Base):
    __tablename__ = "blobs"
    key = Column(String(60), primary_key=True)
    name = Column(String(300))
    mime = Column(String(120))
    data = Column(LargeBinary)


def db_url() -> str:
    env = os.environ.get("DATABASE_URL")
    if env:
        # Heroku / Render / Neon / Supabase hand out postgres:// or postgresql://; SQLAlchemy needs the driver named.
        for prefix in ("postgres://", "postgresql://"):
            if env.startswith(prefix):
                env = "postgresql+psycopg://" + env[len(prefix):]
                break
        return env
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        # Serverless: the project directory is read-only, so fall back to the instance's temp folder.
        # This keeps the demo working without a database, but the log resets whenever the instance does.
        import tempfile
        return "sqlite:///" + os.path.join(tempfile.gettempdir(), "workpaper.db").replace("\\", "/")
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.normpath(os.path.join(here, "..", "..", "data", "workpaper.db"))
    return f"sqlite:///{path}"


_engine = None
_Session = None


def get_sessionmaker(url: str | None = None):
    global _engine, _Session
    if _Session is None or url:
        u = url or db_url()
        if u.startswith("sqlite"):
            kwargs: dict = {"connect_args": {"check_same_thread": False}}
        else:
            # pre_ping survives pooled connections being dropped between serverless invocations
            kwargs = {"pool_pre_ping": True, "pool_recycle": 300}
        _engine = create_engine(u, future=True, **kwargs)
        Base.metadata.create_all(_engine)
        _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _Session


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Event:
    id: str
    seq: int
    at: str
    actor: str
    role: str
    type: str
    target: str | None
    area: str | None
    batch_id: str | None
    undo_of: str | None
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "seq": self.seq, "at": self.at, "actor": self.actor, "role": self.role,
            "type": self.type, "target": self.target, "area": self.area, "batch_id": self.batch_id,
            "undo_of": self.undo_of, "payload": self.payload,
        }


class EventStore:
    def __init__(self, url: str | None = None):
        self.Session = get_sessionmaker(url)
        self._cache: list[Event] | None = None

    def append(self, type: str, actor: str, role: str, payload: dict[str, Any], target: str | None = None,
               area: str | None = None, batch_id: str | None = None, undo_of: str | None = None,
               at: str | None = None) -> Event:
        row = EventRow(id="ev_" + uuid.uuid4().hex[:12], at=at or now_iso(), actor=actor, role=role, type=type,
                       target=target, area=area, batch_id=batch_id, undo_of=undo_of,
                       payload=json.dumps(payload, default=str))
        with self.Session() as s:
            s.add(row)
            s.commit()
            s.refresh(row)
        ev = self._to_event(row)
        if self._cache is not None:
            self._cache.append(ev)
        return ev

    @staticmethod
    def _to_event(row: EventRow) -> Event:
        return Event(id=row.id, seq=row.seq, at=row.at, actor=row.actor, role=row.role, type=row.type,
                     target=row.target, area=row.area, batch_id=row.batch_id, undo_of=row.undo_of,
                     payload=json.loads(row.payload))

    def last_seq(self) -> int:
        with self.Session() as s:
            return s.execute(select(func.max(EventRow.seq))).scalar() or 0

    def all(self) -> list[Event]:
        # The cache is per process. Another process (a second server instance, a serverless worker) may
        # have appended or reset, so one cheap max(seq) query decides whether the cache is still current.
        if self._cache is not None:
            cached = self._cache[-1].seq if self._cache else 0
            if self.last_seq() != cached:
                self._cache = None
        if self._cache is None:
            with self.Session() as s:
                rows = s.execute(select(EventRow).order_by(EventRow.seq)).scalars().all()
            self._cache = [self._to_event(r) for r in rows]
        return list(self._cache)

    def get(self, event_id: str) -> Event | None:
        return next((e for e in self.all() if e.id == event_id), None)

    def put_blob(self, name: str, mime: str, data: bytes) -> str:
        key = "blob_" + uuid.uuid4().hex[:12]
        with self.Session() as s:
            s.add(BlobRow(key=key, name=name, mime=mime, data=data))
            s.commit()
        return key

    def get_blob(self, key: str) -> BlobRow | None:
        with self.Session() as s:
            return s.get(BlobRow, key)

    def reset(self) -> None:
        with self.Session() as s:
            s.query(EventRow).delete()
            s.query(BlobRow).delete()
            s.commit()
        self._cache = []


# ----------------------------------------------------------------------------- projection

def fingerprint(items: Iterable[tuple[str, Any]]) -> str:
    h = hashlib.sha256()
    for k, v in sorted(items, key=lambda kv: kv[0]):
        h.update(f"{k}={json.dumps(v, sort_keys=True, default=str)};".encode())
    return h.hexdigest()[:16]


class State:
    """Workpaper state folded from the event log."""

    def __init__(self, events: list[Event]):
        self.events = events
        self.undone: set[str] = set()
        self.adjustments: dict[str, dict] = {}
        self.verifications: list[dict] = []
        self.notes: dict[str, dict] = {}
        self.questions: dict[str, dict] = {}
        self.attachments: dict[str, dict] = {}
        self.signoffs: dict[str, dict] = {}
        self.assignments: dict[str, dict] = {}
        self.time_entries: list[dict] = []
        self.view_log: list[dict] = []
        self.standards_overrides: dict[str, Any] = {}
        self.filing: dict[str, Any] = {"status": "open", "history": []}
        self.client_approvals: list[dict] = []
        self.read_markers: dict[str, str] = {}
        self.check_overrides: dict[str, dict] = {}
        self.whatifs: dict[str, dict] = {}
        self.carryforward_notes: list[dict] = []
        self._fold()

    def _fold(self) -> None:
        # first pass: undo set (undo events reference an event id or batch id)
        batch_members: dict[str, list[str]] = {}
        for e in self.events:
            if e.batch_id:
                batch_members.setdefault(e.batch_id, []).append(e.id)
        for e in self.events:
            if e.type == "undo":
                tgt = e.payload.get("undone_event_id")
                if tgt:
                    self.undone.add(tgt)
                b = e.payload.get("batch_id")
                if b:
                    self.undone.update(batch_members.get(b, []))
        for e in self.events:
            if e.id in self.undone or e.type == "undo":
                continue
            h = getattr(self, "_on_" + e.type.replace(".", "_"), None)
            if h:
                h(e)

    # -- handlers
    def _on_adjustment_proposed(self, e: Event) -> None:
        p = dict(e.payload)
        p.update(id=e.id, at=e.at, actor=e.actor, role=e.role, line_key=e.target, area=e.area,
                 batch_id=e.batch_id, status=p.get("status", "proposed"))
        self.adjustments[e.id] = p

    def _on_adjustment_approved(self, e: Event) -> None:
        a = self.adjustments.get(e.payload["adjustment_id"])
        if a:
            a.update(status="applied", approved_by=e.actor, approved_at=e.at)

    def _on_adjustment_rejected(self, e: Event) -> None:
        a = self.adjustments.get(e.payload["adjustment_id"])
        if a:
            a.update(status="rejected", rejected_by=e.actor, rejected_at=e.at, rejection_reason=e.payload.get("reason"))

    def _on_verification_recorded(self, e: Event) -> None:
        self.verifications.append({**e.payload, "id": e.id, "at": e.at, "actor": e.actor, "role": e.role, "target": e.target, "area": e.area})

    def _on_note_created(self, e: Event) -> None:
        self.notes[e.id] = {**e.payload, "id": e.id, "at": e.at, "actor": e.actor, "role": e.role, "target": e.target, "area": e.area, "status": "open", "thread": []}

    def _on_note_resolved(self, e: Event) -> None:
        n = self.notes.get(e.payload["note_id"])
        if n:
            n.update(status="resolved", resolved_by=e.actor, resolved_at=e.at, resolution=e.payload.get("resolution"))
            n["thread"].append({"at": e.at, "actor": e.actor, "text": e.payload.get("resolution"), "kind": "resolved"})

    def _on_note_reopened(self, e: Event) -> None:
        n = self.notes.get(e.payload["note_id"])
        if n:
            n.update(status="open", reopened_by=e.actor, reopened_at=e.at)
            n["thread"].append({"at": e.at, "actor": e.actor, "text": e.payload.get("reason"), "kind": "reopened"})

    def _on_note_replied(self, e: Event) -> None:
        n = self.notes.get(e.payload["note_id"])
        if n:
            n["thread"].append({"at": e.at, "actor": e.actor, "text": e.payload.get("text"), "kind": "reply"})

    def _on_question_asked(self, e: Event) -> None:
        self.questions[e.id] = {**e.payload, "id": e.id, "at": e.at, "actor": e.actor, "role": e.role, "target": e.target, "area": e.area, "status": "open"}

    def _on_question_answered(self, e: Event) -> None:
        q = self.questions.get(e.payload["question_id"])
        if q:
            q.update(status="answered", answer=e.payload.get("answer"), answered_by=e.actor, answered_at=e.at, answer_event_id=e.id)

    def _on_attachment_added(self, e: Event) -> None:
        self.attachments[e.id] = {**e.payload, "id": e.id, "at": e.at, "actor": e.actor, "target": e.target, "area": e.area}

    def _on_signoff_given(self, e: Event) -> None:
        self.signoffs[e.id] = {**e.payload, "id": e.id, "at": e.at, "actor": e.actor, "role": e.role, "area": e.area, "status": "active"}

    def _on_signoff_reopened(self, e: Event) -> None:
        s = self.signoffs.get(e.payload["signoff_id"])
        if s:
            s.update(status="reopened", reopened_at=e.at, reopened_cause=e.payload.get("cause"), reopened_by_event=e.payload.get("cause_event_id"))

    def _on_signoff_withdrawn(self, e: Event) -> None:
        s = self.signoffs.get(e.payload["signoff_id"])
        if s:
            s.update(status="withdrawn", withdrawn_at=e.at)

    def _on_assignment_set(self, e: Event) -> None:
        self.assignments[e.payload["area"]] = {**e.payload, "at": e.at, "actor": e.actor}

    def _on_time_logged(self, e: Event) -> None:
        self.time_entries.append({**e.payload, "id": e.id, "at": e.at, "actor": e.actor})

    def _on_view_sensitive(self, e: Event) -> None:
        self.view_log.append({**e.payload, "id": e.id, "at": e.at, "actor": e.actor, "role": e.role})

    def _on_standards_updated(self, e: Event) -> None:
        self.standards_overrides[e.payload["path"]] = {"value": e.payload["value"], "at": e.at, "actor": e.actor}

    def _on_filing_status(self, e: Event) -> None:
        self.filing["status"] = e.payload["status"]
        self.filing["history"].append({**e.payload, "at": e.at, "actor": e.actor, "id": e.id})

    def _on_client_approval(self, e: Event) -> None:
        self.client_approvals.append({**e.payload, "at": e.at, "actor": e.actor, "id": e.id})

    def _on_read_marker(self, e: Event) -> None:
        self.read_markers[e.actor] = e.at

    def _on_check_override(self, e: Event) -> None:
        self.check_overrides[e.payload["check_id"]] = {**e.payload, "at": e.at, "actor": e.actor, "id": e.id}

    def _on_whatif_saved(self, e: Event) -> None:
        self.whatifs[e.id] = {**e.payload, "id": e.id, "at": e.at, "actor": e.actor}

    def _on_carryforward_noted(self, e: Event) -> None:
        self.carryforward_notes.append({**e.payload, "id": e.id, "at": e.at, "actor": e.actor})

    # -- derived views
    def applied_adjustments(self) -> dict[str, list[dict]]:
        """line_key -> applied adjustments in order (last one wins)."""
        out: dict[str, list[dict]] = {}
        for a in self.adjustments.values():
            if a["status"] == "applied":
                out.setdefault(a["line_key"], []).append(a)
        return out

    def effective_value(self, line_key: str, engine_value: Any) -> tuple[Any, dict | None]:
        adjs = self.applied_adjustments().get(line_key)
        if adjs:
            return adjs[-1]["new_value"], adjs[-1]
        return engine_value, None

    def open_blocking_notes(self) -> list[dict]:
        return [n for n in self.notes.values() if n["status"] == "open" and n.get("blocking")]

    def active_signoffs(self, scope: str | None = None) -> list[dict]:
        return [s for s in self.signoffs.values() if s["status"] == "active" and (scope is None or s["scope"] == scope)]

    def is_frozen(self) -> bool:
        return self.filing["status"] in ("accepted", "frozen")

    def events_since(self, actor: str) -> list[Event]:
        marker = self.read_markers.get(actor)
        if not marker:
            return list(self.events)
        return [e for e in self.events if e.at > marker and e.actor != actor]
