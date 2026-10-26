import React, { useContext, useState } from "react";
import { api, fmt } from "../api.js";
import { Ctx } from "../context.js";
import { Chip, Loading, Ref, Who, useAsync } from "../components/ui.jsx";

const LABEL = {
  "adjustment.proposed": "adjusted", "adjustment.approved": "approved adjustment", "adjustment.rejected": "rejected adjustment", "verification.recorded": "verified", "note.created": "noted", "note.resolved": "resolved note", "note.reopened": "reopened note", "note.replied": "replied",
  "question.asked": "asked", "question.answered": "answered", "attachment.added": "attached", "signoff.given": "signed off", "signoff.reopened": "sign-off reopened", "assignment.set": "assigned", "time.logged": "logged time", "view.sensitive": "viewed sensitive data",
  "standards.updated": "changed a standard", "filing.status": "filing status", "client.approval": "client approval", "read.marker": "marked as read", "check.override": "resolved check", "whatif.saved": "saved what-if", "carryforward.noted": "carry-forward note", "undo": "undo",
};

export function describe(e) {
  const p = e.payload || {};
  switch (e.type) {
    case "adjustment.proposed": return <>{e.target}: {fmt(p.old_value)} → <b>{fmt(p.new_value)}</b> · {p.reason} <span className="muted">(fed {fmt(p.tax_effect?.federal)}, CA {fmt(p.tax_effect?.california)}{p.requires_partner ? ", awaiting partner" : ""})</span></>;
    case "verification.recorded": return <>{e.target} · {p.type?.replace(/_/g, " ")} {p.note && <span className="muted">· {p.note}</span>}</>;
    case "note.created": return <>{p.blocking && <Chip tone="bad">blocks filing</Chip>} <Chip>{p.kind}</Chip> {e.target || e.area}: {p.text}</>;
    case "question.asked": return <>→ {p.to === "client" ? "client" : <Who id={p.to} />}: {p.text}</>;
    case "question.answered": return <>{p.answer}</>;
    case "signoff.given": return <>{p.level} on {p.scope} <span className="mono muted">#{p.fingerprint}</span></>;
    case "signoff.reopened": return <span className="delta up">{p.cause}</span>;
    case "filing.status": return <><Chip tone="accent">{p.status}</Chip> {p.detail}</>;
    case "client.approval": return <>{p.approved ? "Approved and signed" : "Declined"} {p.comment}</>;
    case "check.override": return <>{p.check_id} → {p.status}: {p.reason}</>;
    case "time.logged": return <>{p.hours} h on {p.area}</>;
    case "assignment.set": return <>{p.area} → <Who id={p.assignee} />{p.due ? ` by ${p.due}` : ""}</>;
    case "standards.updated": return <>{p.path} = {JSON.stringify(p.value)}</>;
    case "view.sensitive": return <>{p.subject}</>;
    case "undo": return <>undid {p.undone_event_id || `batch ${p.batch_id}`}</>;
    default: return <span className="muted">{JSON.stringify(p).slice(0, 120)}</span>;
  }
}

export default function Activity() {
  const { tick, actor, can, toast, refreshOverview } = useContext(Ctx);
  const [sinceMe, setSinceMe] = useState(true);
  const { data, error, reload } = useAsync(() => api.activity(sinceMe), [tick, sinceMe]);
  const [hideViews, setHideViews] = useState(true);
  async function undo(e) {
    try { await (e.batch_id ? api.undo({ batch_id: e.batch_id }) : api.undo({ event_id: e.id })); toast(e.batch_id ? "Batch undone" : "Undone"); reload(); refreshOverview(); } catch (err) { toast(err.message, true); }
  }
  async function markRead() { await api.readMarker(); toast("Marked as read. Next time you'll see only what changed since now."); reload(); refreshOverview(); }
  if (!data) return <Loading error={error} />;
  const rows = data.filter((e) => !(hideViews && (e.type === "view.sensitive" || e.type === "read.marker")));
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="flex between"><div><h1>Activity</h1><div className="muted">Everything anyone did, in order. Nothing is ever edited in place; undo appends a reversal.</div></div>
        <div className="pill-row"><button className={`btn ${sinceMe ? "primary" : ""}`} onClick={() => setSinceMe(true)}>Since I last looked</button><button className={`btn ${!sinceMe ? "primary" : ""}`} onClick={() => setSinceMe(false)}>Everything</button><button className="btn" onClick={markRead}>Mark all as seen</button><label className="small flex"><input type="checkbox" checked={hideViews} onChange={(e) => setHideViews(e.target.checked)} /> hide view logs</label></div></div>
      <div className="feed">
        {rows.length === 0 && <div className="empty">{sinceMe ? "Nothing changed since you last looked." : "No activity yet."}</div>}
        {rows.map((e) => (
          <div key={e.id} className={`item ${e.undone ? "undone" : ""}`}>
            <div className="small muted mono">{e.at.slice(5, 16).replace("T", " ")}</div>
            <div className="small"><b><Who id={e.actor} /></b> <span className="muted">{LABEL[e.type] || e.type}</span> {e.target && <Ref r={e.target} />} <span style={{ marginLeft: 4 }}>{describe(e)}</span>{e.batch_id && <Chip tone="ghost">batch</Chip>}</div>
            <div>{can("undo") && !e.undone && e.type !== "undo" && (e.actor === actor.id || ["partner", "firm_administrator"].includes(actor.role)) && <button className="btn small" onClick={() => undo(e)}>Undo{e.batch_id ? " batch" : ""}</button>}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
