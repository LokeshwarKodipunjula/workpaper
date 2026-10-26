import React, { useContext } from "react";
import { Link } from "react-router-dom";
import { fmt, fmtDate } from "../api.js";
import { Ctx } from "../context.js";
import { Bar, Chip, Delta, Loading, STATUS_LABEL, STATUS_TONE, Who } from "../components/ui.jsx";

export default function Overview() {
  const { overview: o, openRef, meta } = useContext(Ctx);
  if (!o) return <Loading />;
  const s = o.summary;
  const ws = s.working_summary;
  const owe = (v) => (v >= 0 ? `owe ${fmt(v)}` : `refund ${fmt(-v)}`);
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="flex between">
        <div><h1>Okafor-Lindqvist · 2025 joint return</h1><div className="muted">Engine {s.version} computed {fmtDate(s.computed_at)} · {meta.household.people.length} people · moved CA → TX 2025-07-15 · filing status <b>{o.filing.status.replace(/_/g, " ")}</b></div></div>
        <div className="pill-row"><Link className="btn" to="/checks">Checks: {o.checks.fail} failing · {o.checks.warn} warnings</Link><Link className="btn" to="/activity">{o.since_you_looked} changes since you last looked</Link></div>
      </div>

      <div className="grid4">
        <div className="stat"><div className="label">Federal · working</div><div className="value">{owe(ws.federal.balance_due_working)}</div><div className="sub">engine {owe(ws.federal.balance_due)} · total tax {fmt(ws.federal.total_tax_working)} ({ws.adjustment_effect.federal >= 0 ? "+" : ""}{fmt(ws.adjustment_effect.federal)} from adjustments)</div></div>
        <div className="stat"><div className="label">California · working</div><div className="value">{owe(ws.california.balance_due_working)}</div><div className="sub">engine {owe(ws.california.balance_due)} · total tax {fmt(ws.california.total_tax_working)} ({ws.adjustment_effect.california >= 0 ? "+" : ""}{fmt(ws.adjustment_effect.california)})</div></div>
        <div className="stat"><div className="label">Open items</div><div className="value">{o.open_notes.length + o.open_questions.length}</div><div className="sub">{o.open_notes.filter((n) => n.blocking).length} block filing · {o.open_questions.filter((q) => q.to === "client").length} with the client</div></div>
        <div className="stat"><div className="label">Sign-offs</div><div className="value">{o.signoffs.filter((x) => x.status === "active").length}<span className="muted" style={{ fontSize: 13 }}> active</span></div><div className="sub">{o.signoffs.filter((x) => x.status === "reopened").length} reopened by later changes</div></div>
      </div>

      <div className="grid2">
        <div className="card">
          <h2>Return summary vs last year</h2>
          <table className="dense"><thead><tr><th>Line</th><th className="right">2025</th><th className="right">change vs 2024</th></tr></thead><tbody>
            {s.federal.map((r) => <tr key={r.key} className="clickable" onClick={() => openRef(r.key)}><td>{r.label} <span className="key">{r.key}</span>{r.adjusted && <Chip tone="purple">adj</Chip>}</td><td className="num"><b>{fmt(r.value)}</b></td><td className="right"><Delta variance={r.variance} /></td></tr>)}
          </tbody></table>
          <div className="muted small" style={{ marginTop: 6 }}>2024 was a full-year California return by a different preparer, so some swings are expected. Flagged swings (over 10% and 1,000) need a variance note.</div>
        </div>
        <div className="card">
          <h2>Areas</h2>
          <table className="dense"><thead><tr><th>Area</th><th>Status</th><th className="right">Lines</th><th className="right">Verified</th><th className="right">Checks</th><th className="right">Hours / budget</th><th>Owner</th></tr></thead><tbody>
            {o.areas.map((a) => (
              <tr key={a.id} className="clickable" onClick={() => (window.location.hash = "", null)}>
                <td><Link to={`/area/${a.id}`}>{a.title}</Link></td>
                <td><Chip tone={STATUS_TONE[a.status]}>{STATUS_LABEL[a.status] || a.status}</Chip></td>
                <td className="num">{a.lines}</td>
                <td className="num">{a.lines ? Math.round((a.verified / a.lines) * 100) : 0}%</td>
                <td className="num">{a.checks_failing ? <span className="delta up">{a.checks_failing} fail</span> : ""} {a.checks_warning ? <span className="delta flat">{a.checks_warning} warn</span> : ""}</td>
                <td className="num" style={{ minWidth: 110 }}>{a.hours_logged.toFixed(1)} / {a.budget_hours ?? "—"}<Bar value={a.hours_logged} max={a.budget_hours || 0} /></td>
                <td className="small">{a.assignment ? <Who id={a.assignment.assignee} /> : <span className="muted">—</span>}</td>
              </tr>
            ))}
          </tbody></table>
        </div>
      </div>

      <div className="grid3">
        <div className="card">
          <h2>Open review notes</h2>
          {o.open_notes.length === 0 && <div className="muted small">None.</div>}
          {o.open_notes.slice(0, 8).map((n) => <div key={n.id} className="small" style={{ padding: "4px 0", borderBottom: "1px solid var(--line)" }}><Chip tone={n.blocking ? "bad" : "warn"}>{n.blocking ? "blocks filing" : n.kind}</Chip> {n.target && <a className="reflink" onClick={() => openRef(n.target)}>{n.target}</a>} {n.text.slice(0, 110)} <span className="muted">· <Who id={n.actor} /></span></div>)}
        </div>
        <div className="card">
          <h2>Questions outstanding</h2>
          {o.open_questions.length === 0 && <div className="muted small">None.</div>}
          {o.open_questions.slice(0, 8).map((q) => <div key={q.id} className="small" style={{ padding: "4px 0", borderBottom: "1px solid var(--line)" }}><Chip tone="warn">→ {q.to === "client" ? "client" : <Who id={q.to} />}</Chip> {q.target && <a className="reflink" onClick={() => openRef(q.target)}>{q.target}</a>} {q.text.slice(0, 110)}{q.due && <span className="muted"> · due {q.due}</span>}</div>)}
        </div>
        <div className="card">
          <h2>Deadlines</h2>
          {o.deadlines.map((d, i) => <div key={i} className="flex between small" style={{ padding: "3px 0", borderBottom: "1px solid var(--line)" }}><span>{d.what}</span><span className="mono nowrap">{d.date}</span></div>)}
        </div>
      </div>
    </div>
  );
}
