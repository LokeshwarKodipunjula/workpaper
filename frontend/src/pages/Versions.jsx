import React, { useContext, useState } from "react";
import { api, fmt, fmtDate } from "../api.js";
import { Ctx } from "../context.js";
import { Chip, Loading, Ref, useAsync } from "../components/ui.jsx";

export default function Versions() {
  const { meta, openRef } = useContext(Ctx);
  const ids = meta.versions.map((v) => v.version);
  const [a, setA] = useState(ids[ids.length - 2] || ids[0]);
  const [b, setB] = useState(ids[ids.length - 1]);
  const { data, error } = useAsync(() => api.compare(a, b), [a, b]);
  const [onlyUndeclared, setOnlyUndeclared] = useState(false);
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div><h1>Versions & compare</h1><div className="muted">Three engine runs as documents arrived. Compare any two: what changed, which documents drove it, and whether the engine declared every change it made.</div></div>
      <div className="grid3">
        {meta.versions.map((v) => <div key={v.version} className="card tight"><div className="flex between"><b>{v.version}</b><span className="muted small">{fmtDate(v.computed_at)}</span></div><div className="small" style={{ margin: "4px 0" }}>{v.trigger}</div><div className="small muted">{v.documents_used.length} documents used{v.documents_superseded?.length ? ` · superseded ${v.documents_superseded.join(", ")}` : ""} · {v.diagnostics?.length} diagnostics</div><div className="small" style={{ marginTop: 4 }}>Fed tax {fmt(v.summary.federal.total_tax)} · owe {fmt(v.summary.federal.balance_due)} · CA tax {fmt(v.summary.california.total_tax)} · CA {v.summary.california.balance_due < 0 ? "refund" : "owe"} {fmt(Math.abs(v.summary.california.balance_due))}</div></div>)}
      </div>
      <div className="toolbar"><span>Compare</span><select value={a} onChange={(e) => setA(e.target.value)}>{ids.map((i) => <option key={i}>{i}</option>)}</select><span>→</span><select value={b} onChange={(e) => setB(e.target.value)}>{ids.map((i) => <option key={i}>{i}</option>)}</select><label className="small flex"><input type="checkbox" checked={onlyUndeclared} onChange={(e) => setOnlyUndeclared(e.target.checked)} /> only changes the engine did not declare</label></div>
      {!data ? <Loading error={error} /> : (() => {
        const declared = new Set(data.declared_changes.map((c) => c.key));
        const rows = data.rows.filter((r) => !onlyUndeclared || !declared.has(r.key));
        return (
          <div className="stack">
            <div className="grid3">
              <div className="stat"><div className="label">Lines changed</div><div className="value">{data.rows.length}</div><div className="sub">{data.rows.filter((r) => !declared.has(r.key)).length} not in the engine's change list</div></div>
              <div className="stat"><div className="label">Documents added</div><div className="value">{data.documents_added.length}</div><div className="sub pill-row">{data.documents_added.map((d) => <Ref key={d} r={d} />)}</div></div>
              <div className="stat"><div className="label">Federal total tax</div><div className="value">{fmt(data.summary_a.federal.total_tax)} → {fmt(data.summary_b.federal.total_tax)}</div><div className="sub">balance due {fmt(data.summary_a.federal.balance_due)} → {fmt(data.summary_b.federal.balance_due)}</div></div>
            </div>
            <div className="card"><table className="dense"><thead><tr><th>Line</th><th>Label</th><th className="right">{a}</th><th className="right">{b}</th><th className="right">Δ</th><th>Declared</th></tr></thead><tbody>
              {rows.map((r) => <tr key={r.key} className="clickable" onClick={() => openRef(r.key)}><td className="key">{r.key}</td><td className="small">{r.label}</td><td className="num">{fmt(r.a, {})}</td><td className="num"><b>{fmt(r.b, {})}</b></td><td className="num">{typeof r.a === "number" && typeof r.b === "number" ? fmt(r.b - r.a, {}) : r.change}</td><td>{declared.has(r.key) ? <Chip tone="ok">yes</Chip> : <Chip tone="warn">undeclared</Chip>}</td></tr>)}
            </tbody></table></div>
          </div>
        );
      })()}
    </div>
  );
}
