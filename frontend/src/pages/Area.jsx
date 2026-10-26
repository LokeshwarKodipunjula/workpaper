import React, { useContext, useState } from "react";
import { useParams } from "react-router-dom";
import { api, fmtDate } from "../api.js";
import { Ctx } from "../context.js";
import { Bar, Chip, Loading, Modal, STATUS_LABEL, STATUS_TONE, Who, useAsync } from "../components/ui.jsx";
import LinesTable from "../components/LinesTable.jsx";
import { NoteForm, AskForm } from "../components/forms.jsx";
import { CheckRow } from "./Checks.jsx";
import { NoteRow } from "../components/TracePanel.jsx";

export default function AreaPage() {
  const { id } = useParams();
  const { meta, overview, openRef, tick, can, toast, refreshOverview } = useContext(Ctx);
  const area = meta.areas.find((a) => a.id === id);
  const lines = useAsync(() => api.lines({ area: id }), [id, tick]);
  const checks = useAsync(() => api.checks({ area: id }), [id, tick]);
  const docs = useAsync(() => api.documents(), [tick]);
  const [tab, setTab] = useState("lines");
  const [modal, setModal] = useState(null);
  const [hours, setHours] = useState("");
  const summary = overview?.areas.find((a) => a.id === id);
  if (!area) return <div className="empty">Unknown area</div>;
  const areaDocs = (docs.data || []).filter((d) => d.area === id);
  const openNotes = (overview?.open_notes || []).filter((n) => n.area === id);
  const done = () => { setModal(null); lines.reload(); checks.reload(); refreshOverview(); };

  async function sign(level) {
    try { await api.signoff({ scope: id, level }); toast(`${level} sign-off recorded. It reopens automatically if anything in this area changes.`); refreshOverview(); } catch (e) { toast(e.message, true); }
  }
  async function logTime() {
    try { await api.time({ area: id, hours: parseFloat(hours) }); setHours(""); toast("Time logged"); refreshOverview(); } catch (e) { toast(e.message, true); }
  }

  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="flex between wrap">
        <div><h1>{area.title}</h1><div className="muted">{area.description}</div></div>
        {summary && <div className="pill-row">
          <Chip tone={STATUS_TONE[summary.status]}>{STATUS_LABEL[summary.status] || summary.status}</Chip>
          {summary.signoffs.map((s) => <Chip key={s.id} tone={s.status === "active" ? "ok" : "warn"} title={`${s.actor} ${fmtDate(s.at)}`}>{s.level} {s.status === "active" ? "✓" : "reopened"}</Chip>)}
        </div>}
      </div>

      <div className="grid4">
        <div className="stat"><div className="label">Lines</div><div className="value">{summary?.lines}</div><div className="sub">{summary?.verified} verified · {summary?.adjusted} adjusted</div></div>
        <div className="stat"><div className="label">Checks</div><div className="value">{summary?.checks_failing}<span className="muted" style={{ fontSize: 13 }}> failing</span></div><div className="sub">{summary?.checks_warning} warnings · {summary?.flagged_variances} swings vs 2024</div></div>
        <div className="stat"><div className="label">Open</div><div className="value">{(summary?.open_notes || 0) + (summary?.open_questions || 0)}</div><div className="sub">{summary?.blocking_notes} blocking · {summary?.open_questions} questions</div></div>
        <div className="stat"><div className="label">Time vs budget</div><div className="value">{summary?.hours_logged?.toFixed(1)} / {summary?.budget_hours ?? "—"} h</div><Bar value={summary?.hours_logged || 0} max={summary?.budget_hours || 0} />
          {can("time") && <div className="flex" style={{ marginTop: 6 }}><input style={{ width: 70 }} placeholder="hrs" value={hours} onChange={(e) => setHours(e.target.value)} /><button className="btn small" disabled={!hours} onClick={logTime}>Log</button></div>}
        </div>
      </div>

      <div className="toolbar">
        {can("signoff_preparer") && <button className="btn" onClick={() => sign("preparer")}>Preparer sign-off</button>}
        {can("signoff_reviewer") && <button className="btn" onClick={() => sign("reviewer")}>Reviewer sign-off</button>}
        {can("signoff_partner") && <button className="btn primary" onClick={() => sign("partner")}>Partner sign-off</button>}
        {can("note") && <button className="btn" onClick={() => setModal("note")}>Area note / judgment</button>}
        {can("question_client") && <button className="btn" onClick={() => setModal("ask")}>Ask client</button>}
        <div className="spacer" />
        {summary?.assignment && <span className="small muted">Assigned to <Who id={summary.assignment.assignee} />{summary.assignment.due ? ` · due ${summary.assignment.due}` : ""}</span>}
      </div>

      <div className="tabs">
        <button className={tab === "lines" ? "active" : ""} onClick={() => setTab("lines")}>Lines</button>
        <button className={tab === "checks" ? "active" : ""} onClick={() => setTab("checks")}>Checks ({checks.data?.filter((c) => ["fail", "warn"].includes(c.status)).length ?? "…"})</button>
        <button className={tab === "docs" ? "active" : ""} onClick={() => setTab("docs")}>Documents ({areaDocs.length})</button>
        <button className={tab === "notes" ? "active" : ""} onClick={() => setTab("notes")}>Open notes ({openNotes.length})</button>
      </div>

      {tab === "lines" && (lines.data ? <div className="card"><LinesTable lines={lines.data} onReload={done} /></div> : <Loading error={lines.error} />)}
      {tab === "checks" && (checks.data ? <div className="stack">{checks.data.length === 0 && <div className="empty">No checks in this area.</div>}{checks.data.map((c) => <CheckRow key={c.id} c={c} onDone={done} />)}</div> : <Loading error={checks.error} />)}
      {tab === "docs" && <div className="card"><table className="dense"><thead><tr><th>Doc</th><th>Title</th><th>Received</th><th>Status</th><th className="right">Values landed</th><th>Lines</th></tr></thead><tbody>
        {areaDocs.map((d) => <tr key={d.id} className="clickable" onClick={() => openRef(d.id)}><td className="key">{d.id}</td><td>{d.title}{d.why_not && <div className="muted small">{d.why_not}</div>}</td><td className="small">{fmtDate(d.received_at)}</td><td><span className="pill-row">{d.marked_corrected && <Chip tone="warn">corrected</Chip>}{d.superseded && <Chip tone="bad">superseded</Chip>}{!d.used_by_engine && !d.superseded && <Chip tone="warn">not used</Chip>}{d.extraction_status === "partial" && <Chip tone="bad">partial</Chip>}{d.low_confidence_values > 0 && <Chip tone="warn">{d.low_confidence_values} low-conf</Chip>}{d.verified && <Chip tone="ok">✓</Chip>}</span></td><td className="num">{d.values_landed}/{d.values_total}</td><td className="small muted">{d.lines.slice(0, 5).join(", ")}{d.lines.length > 5 ? ` +${d.lines.length - 5}` : ""}</td></tr>)}
      </tbody></table></div>}
      {tab === "notes" && <div className="stack">{openNotes.length === 0 && <div className="empty">No open notes.</div>}{openNotes.map((n) => <NoteRow key={n.id} n={n} onDone={done} />)}</div>}

      {modal === "note" && <Modal title={`Note on ${area.title}`} onClose={() => setModal(null)}><NoteForm area={id} onDone={done} defaultKind="judgment" /></Modal>}
      {modal === "ask" && <Modal title={`Ask about ${area.title}`} onClose={() => setModal(null)}><AskForm area={id} onDone={done} /></Modal>}
    </div>
  );
}
