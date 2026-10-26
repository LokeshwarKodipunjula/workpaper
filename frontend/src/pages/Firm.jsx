import React, { useContext, useState } from "react";
import { api, fmtDate } from "../api.js";
import { Ctx } from "../context.js";
import { Bar, Chip, Loading, Who, useAsync } from "../components/ui.jsx";

export default function Firm() {
  const { tick, can, toast, meta, refreshOverview } = useContext(Ctx);
  const { data, error, reload } = useAsync(() => api.firm(), [tick]);
  const [pct, setPct] = useState("");
  const [amt, setAmt] = useState("");
  const [newRule, setNewRule] = useState("");
  const [assign, setAssign] = useState({ area: "", assignee: "", due: "" });
  if (!data) return <Loading error={error} />;
  const std = data.standards;
  async function saveStd(path, value) { try { await api.standards({ path, value }); toast("Standard updated firm-wide"); reload(); refreshOverview(); } catch (e) { toast(e.message, true); } }
  async function doAssign() { try { await api.assign(assign); toast("Assigned"); setAssign({ area: "", assignee: "", due: "" }); refreshOverview(); } catch (e) { toast(e.message, true); } }
  async function demo(kind) { try { if (kind === "reset") { await api.reset(); toast("All workpaper events cleared"); } else { const r = await api.seed(); toast(`Season replayed: ${r.seeded} events`); } reload(); refreshOverview(); } catch (e) { toast(e.message, true); } }
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div><h1>Firm: standards, people, time, protection</h1><div className="muted">{data.firm.name}. Standards apply to every return; changing one here changes what the checks flag and what the sign-off rules enforce.</div></div>
      <div className="grid2">
        <div className="card">
          <h2>Standards</h2>
          <h3>Variance review</h3>
          <div className="small">Flag a line when it moves more than <b>{std.variance_review.flag_if_change_over_percent}%</b> and more than <b>{std.variance_review.and_over_amount.toLocaleString()}</b> versus {std.variance_review.compare_to.replace("_", " ")}.</div>
          {can("standards") && <div className="flex" style={{ marginTop: 6 }}><input style={{ width: 70 }} placeholder="%" value={pct} onChange={(e) => setPct(e.target.value)} /><button className="btn small" disabled={!pct} onClick={() => saveStd("variance_review.flag_if_change_over_percent", +pct)}>Set %</button><input style={{ width: 90 }} placeholder="amount" value={amt} onChange={(e) => setAmt(e.target.value)} /><button className="btn small" disabled={!amt} onClick={() => saveStd("variance_review.and_over_amount", +amt)}>Set amount</button></div>}
          <h3 style={{ marginTop: 10 }}>Verification types</h3><div className="pill-row">{std.verification_types.map((t) => <Chip key={t}>{t.replace(/_/g, " ")}</Chip>)}</div>
          <h3 style={{ marginTop: 10 }}>Rules (enforced by the workpaper)</h3>
          <ol className="small" style={{ paddingLeft: 18 }}>{std.rules.map((r, i) => <li key={i}>{r}</li>)}</ol>
          {can("standards") && <div className="flex"><input className="grow" placeholder="Add a firm rule…" value={newRule} onChange={(e) => setNewRule(e.target.value)} /><button className="btn small" disabled={!newRule} onClick={() => saveStd("rules", [...std.rules, newRule]).then(() => setNewRule(""))}>Add</button></div>}
          <h3 style={{ marginTop: 10 }}>Required steps</h3><ol className="small" style={{ paddingLeft: 18 }}>{std.required_steps.map((r, i) => <li key={i}>{r}</li>)}</ol>
          {Object.keys(data.overrides).length > 0 && <div className="small muted" style={{ marginTop: 8 }}>Changed from the starter standards: {Object.entries(data.overrides).map(([k, v]) => <div key={k}>{k} → {JSON.stringify(v.value)} (<Who id={v.actor} /> {fmtDate(v.at)})</div>)}</div>}
        </div>
        <div className="stack">
          <div className="card">
            <h2>People & roles</h2>
            <table className="dense"><thead><tr><th>Name</th><th>Role</th><th>Credential</th><th>Clearance</th><th>Active from</th></tr></thead><tbody>
              {data.firm.staff.map((s) => <tr key={s.id}><td>{s.name}</td><td>{s.role.replace("_", " ")}</td><td>{s.credential || "—"}</td><td>{s.sensitive_data_clearance ? <Chip tone="ok">yes</Chip> : <Chip tone="bad">masked · views logged</Chip>}</td><td className="mono small">{s.active_from}{s.note ? <div className="muted">{s.note}</div> : null}</td></tr>)}
            </tbody></table>
            <div className="small muted" style={{ marginTop: 6 }}>Starting assignment: preparer <Who id={data.firm.assignment_at_start.preparer} />, reviewer <Who id={data.firm.assignment_at_start.reviewer} />, partner <Who id={data.firm.assignment_at_start.partner} />. Paid preparer signing: Helen Strand.</div>
          </div>
          <div className="card">
            <h2>Assignments & deadlines</h2>
            <table className="dense"><tbody>{meta.areas.map((a) => { const as = data.assignments[a.id]; return <tr key={a.id}><td>{a.title}</td><td>{as ? <><Who id={as.assignee} />{as.due ? <span className="muted"> · due {as.due}</span> : ""}</> : <span className="muted">unassigned</span>}</td></tr>; })}</tbody></table>
            {can("assign") && <div className="flex wrap" style={{ marginTop: 8 }}><select value={assign.area} onChange={(e) => setAssign({ ...assign, area: e.target.value })}><option value="">area…</option>{meta.areas.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}</select><select value={assign.assignee} onChange={(e) => setAssign({ ...assign, assignee: e.target.value })}><option value="">person…</option>{meta.actors.filter((x) => x.kind === "staff").map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select><input type="date" value={assign.due} onChange={(e) => setAssign({ ...assign, due: e.target.value })} /><button className="btn small primary" disabled={!assign.area || !assign.assignee} onClick={doAssign}>Assign</button></div>}
            <div className="small muted" style={{ marginTop: 8 }}>{data.firm.deadlines.map((d, i) => <div key={i}>{d.date} · {d.what}</div>)}</div>
          </div>
        </div>
      </div>
      <div className="grid2">
        <div className="card">
          <h2>Time against budget</h2>
          <table className="dense"><tbody>{Object.entries(data.time.budget).map(([k, b]) => { const h = data.time.by_area[k] || 0; return <tr key={k}><td>{k.replace(/_/g, " ")}</td><td className="num">{h.toFixed(1)} / {b} h</td><td style={{ width: 160 }}><Bar value={h} max={b} /></td></tr>; })}</tbody></table>
          <div className="small muted" style={{ marginTop: 6 }}>Total {Object.values(data.time.by_area).reduce((a, b) => a + b, 0).toFixed(1)} of {Object.values(data.time.budget).reduce((a, b) => a + b, 0)} budgeted hours.</div>
        </div>
        <div className="card">
          <h2>Sensitive-data view log</h2>
          {data.view_log === null ? <div className="muted small">Only the firm administrator and partners see the view log.</div> : data.view_log.length === 0 ? <div className="muted small">No unmasked views yet.</div> : <table className="dense"><tbody>{data.view_log.slice(-30).reverse().map((v) => <tr key={v.id}><td className="mono small">{v.at.slice(0, 16)}</td><td><Who id={v.actor} /></td><td className="small">{v.role}</td><td className="small">{v.field} · {v.subject}</td></tr>)}</tbody></table>}
        </div>
      </div>
      {can("standards") && <div className="card"><h2>Demo controls</h2><div className="small muted">Replay the season: seeds the event log with the actions the firm took from January to the 2028 examination letter, so every role has something to look at. Reset clears every event (the packet is never touched).</div><div className="pill-row" style={{ marginTop: 8 }}><button className="btn primary" onClick={() => demo("seed")}>Replay the season</button><button className="btn danger" onClick={() => demo("reset")}>Reset workpaper</button></div></div>}
    </div>
  );
}
