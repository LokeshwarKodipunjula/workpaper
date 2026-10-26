import React, { useContext, useEffect, useState } from "react";
import { api, fmt } from "../api.js";
import { Ctx } from "../context.js";
import { Chip, Loading, Ref, useAsync } from "../components/ui.jsx";

const CATEGORIES = ["wages", "interest", "schc_profit", "stcg", "ltcg", "ordinary_income", "adjustment", "salt", "itemized", "ca_source_income"];

/** Try what-ifs without touching the return: estimated with the engine's per-dollar rates, plus the engine's own priced alternatives. */
export default function WhatIf() {
  const { toast, can } = useContext(Ctx);
  const tl = useAsync(() => api.timeline(), []);
  const [rows, setRows] = useState([{ line_key: "SchC.27a", new_value: "", category: "schc_profit" }]);
  const [name, setName] = useState("Scenario");
  const [result, setResult] = useState(null);
  const valid = rows.filter((r) => r.line_key && r.new_value !== "" && !isNaN(parseFloat(r.new_value)));
  useEffect(() => {
    if (!valid.length) { setResult(null); return; }
    const t = setTimeout(() => api.whatif({ name, adjustments: valid.map((r) => ({ line_key: r.line_key, new_value: parseFloat(r.new_value), category: r.category })) }).then(setResult).catch((e) => toast(e.message, true)), 250);
    return () => clearTimeout(t);
  }, [JSON.stringify(valid)]);
  async function save() { try { await api.whatif({ name, adjustments: valid.map((r) => ({ line_key: r.line_key, new_value: parseFloat(r.new_value), category: r.category })) }, true); toast("Scenario saved to the record"); } catch (e) { toast(e.message, true); } }
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div><h1>What-if</h1><div className="muted">Change any line hypothetically and see the estimated federal and California effect using the engine's per-dollar rates at this version's numbers. Nothing here changes the return until you record it as an adjustment from the line itself.</div></div>
      <div className="grid2">
        <div className="card">
          <div className="flex between"><h2>Scenario</h2><input value={name} onChange={(e) => setName(e.target.value)} /></div>
          <table className="dense"><thead><tr><th>Line key</th><th>New value</th><th>Rate category</th><th></th></tr></thead><tbody>
            {rows.map((r, i) => <tr key={i}><td><input value={r.line_key} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, line_key: e.target.value } : x))} placeholder="e.g. SchA.11" /></td><td><input value={r.new_value} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, new_value: e.target.value } : x))} /></td><td><select value={r.category} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, category: e.target.value } : x))}>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select></td><td><button className="btn small" onClick={() => setRows(rows.filter((_, j) => j !== i))}>×</button></td></tr>)}
          </tbody></table>
          <div className="pill-row" style={{ marginTop: 8 }}><button className="btn small" onClick={() => setRows([...rows, { line_key: "", new_value: "", category: "ordinary_income" }])}>Add line</button>{can("whatif") && <button className="btn small primary" disabled={!result} onClick={save}>Save scenario to record</button>}</div>
          {result && <div className="stack" style={{ marginTop: 12 }}>
            <div className="grid2"><div className="stat"><div className="label">Federal tax change</div><div className="value">{fmt(result.federal_tax_change)}</div><div className="sub">balance after: {fmt(result.federal_balance_after)}</div></div><div className="stat"><div className="label">California tax change</div><div className="value">{fmt(result.california_tax_change)}</div><div className="sub">balance after: {fmt(result.california_balance_after)}</div></div></div>
            <table className="dense"><tbody>{result.rows.map((r) => <tr key={r.line_key}><td><Ref r={r.line_key} /> <span className="small">{r.label}</span></td><td className="num">{fmt(r.old)} → {fmt(r.new)}</td><td className="num">fed {fmt(r.effect.federal)} · CA {fmt(r.effect.california)}</td><td>{r.effect.requires_partner && <Chip tone="warn">partner</Chip>}</td></tr>)}</tbody></table>
            <div className="muted small">Rates are measured at this version's numbers; large changes can cross thresholds (the real system recomputes). Business adjustments also move the QBI deduction, which the adjustment rate does not capture.</div>
          </div>}
        </div>
        <div className="card">
          <h2>Alternatives the engine has already priced</h2>
          {!tl.data ? <Loading /> : tl.data.what_if.alternatives.map((a) => <div key={a.id} className="card tight" style={{ marginBottom: 8 }}>
            <div className="flex between"><b>{a.description}</b><Chip>{a.base_version}</Chip></div>
            <div className="small" style={{ marginTop: 4 }}>Federal: tax {fmt(a.federal.base.total_tax)} → {fmt(a.federal.alternative.total_tax)} (<b>{fmt(a.federal.total_tax_change)}</b>){a.federal.penalty_change ? `, penalty ${fmt(a.federal.penalty_change)}` : ""} · California: {fmt(a.california.base.total_tax)} → {fmt(a.california.alternative.total_tax)} (<b>{fmt(a.california.total_tax_change)}</b>)</div>
            {a.changed_lines?.length > 0 && <details><summary>{a.changed_lines.length} lines change</summary><table className="dense"><tbody>{a.changed_lines.map((c, i) => <tr key={i}><td><Ref r={c.key} /></td><td className="num">{fmt(c.old)} → {fmt(c.new)}</td></tr>)}</tbody></table></details>}
          </div>)}
          {tl.data && <div className="card tight"><b>Extension estimate (April 14, from v2)</b><div className="small">Federal estimated tax {fmt(tl.data.what_if.extension.federal.estimated_total_tax)}, payments {fmt(tl.data.what_if.extension.federal.payments)}, paid with Form 4868 <b>{fmt(tl.data.what_if.extension.federal.paid_with_form_4868)}</b> ({tl.data.what_if.extension.federal.rule}). California balance {fmt(tl.data.what_if.extension.california.estimated_balance)}: paid 0.</div></div>}
        </div>
      </div>
    </div>
  );
}
