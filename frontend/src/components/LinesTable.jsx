import React, { useContext, useMemo, useState } from "react";
import { fmt } from "../api.js";
import { Ctx } from "../context.js";
import { Chip, Delta, Modal } from "./ui.jsx";
import { VerifyForm } from "./forms.jsx";

/** Lines grouped by form with selection for bulk actions. Large detail (F8949 lots) is collapsed to exceptions by default. */
export default function LinesTable({ lines, onReload, collapseLots = true }) {
  const { openRef, drawer, can } = useContext(Ctx);
  const [sel, setSel] = useState(new Set());
  const [modal, setModal] = useState(null);
  const [showLots, setShowLots] = useState(!collapseLots);
  const [filter, setFilter] = useState("all");

  const groups = useMemo(() => {
    const g = new Map();
    for (const l of lines) {
      if (filter === "unverified" && l.verified) continue;
      if (filter === "adjusted" && !l.adjusted && !l.pending_adjustments?.length) continue;
      if (filter === "swings" && !l.variance?.flagged) continue;
      if (filter === "notes" && !l.open_notes) continue;
      if (!g.has(l.form)) g.set(l.form, []);
      g.get(l.form).push(l);
    }
    return [...g.entries()];
  }, [lines, filter]);

  function toggle(k) { const s = new Set(sel); if (s.has(k)) s.delete(k); else s.add(k); setSel(s); }
  function toggleAll(ls) { const s = new Set(sel); const all = ls.every((l) => s.has(l.key)); for (const l of ls) { if (all) s.delete(l.key); else s.add(l.key); } setSel(s); }

  return (
    <div>
      <div className="toolbar">
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All lines</option><option value="unverified">Unverified</option><option value="adjusted">Adjusted / pending</option><option value="swings">Swings vs 2024</option><option value="notes">With open notes</option>
        </select>
        <span className="muted small">{lines.length} lines · {lines.filter((l) => l.verified).length} verified · {lines.filter((l) => l.adjusted).length} adjusted</span>
        <div className="spacer" />
        {sel.size > 0 && can("verify") && <><Chip tone="accent">{sel.size} selected</Chip><button className="btn small primary" onClick={() => setModal("verify")}>Verify selected</button><button className="btn small" onClick={() => setSel(new Set())}>Clear</button></>}
      </div>
      <table className="dense">
        <thead><tr><th style={{ width: 24 }}></th><th>Line</th><th>Label</th><th className="right">2025</th><th className="right">vs 2024</th><th>Evidence</th><th>State</th></tr></thead>
        <tbody>
          {groups.map(([form, ls]) => {
            const isLots = form === "F8949";
            const visible = isLots && !showLots ? ls.filter((l) => l.adjusted || l.open_notes || l.note || /basis 0\.00/.test(l.label) || l.pending_adjustments?.length) : ls;
            return (
              <React.Fragment key={form}>
                <tr className="group"><td><input type="checkbox" checked={ls.every((l) => sel.has(l.key))} onChange={() => toggleAll(ls)} /></td><td colSpan={6}>
                  {form} · {ls.length} lines {isLots && <button className="btn small" style={{ marginLeft: 8 }} onClick={() => setShowLots(!showLots)}>{showLots ? "Show exceptions only" : `Show all ${ls.length} lots (${visible.length} exceptions shown)`}</button>}
                </td></tr>
                {visible.map((l) => (
                  <tr key={l.key} className={`clickable ${drawer?.id === l.key ? "selected" : ""}`} onClick={() => openRef(l.key)}>
                    <td onClick={(e) => e.stopPropagation()}><input type="checkbox" checked={sel.has(l.key)} onChange={() => toggle(l.key)} /></td>
                    <td className="key">{l.line}</td>
                    <td>{l.label}{l.note && <div className="muted small">{l.note}</div>}</td>
                    <td className="num">{l.adjusted && <span className="muted small" style={{ textDecoration: "line-through", marginRight: 6 }}>{fmt(l.engine_value, {})}</span>}<b>{fmt(l.value, {})}</b></td>
                    <td className="right"><Delta variance={l.variance} /></td>
                    <td className="small muted">{l.source_count ? `${l.source_count} source${l.source_count > 1 ? "s" : ""}` : l.inputs?.length ? `${l.inputs.length} inputs` : "—"}</td>
                    <td><span className="pill-row">
                      {l.verified ? <Chip tone="ok">✓</Chip> : <span className="dot info" title="unverified" />}
                      {l.adjusted && <Chip tone="purple">adj</Chip>}
                      {l.pending_adjustments?.length > 0 && <Chip tone="warn">pending</Chip>}
                      {l.open_notes > 0 && <Chip tone="bad">{l.open_notes}</Chip>}
                      {l.questions?.some((q) => q.status === "open") && <Chip tone="warn">?</Chip>}
                    </span></td>
                  </tr>
                ))}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
      {modal === "verify" && <Modal title={`Verify ${sel.size} lines`} onClose={() => setModal(null)}><VerifyForm targets={[...sel]} onDone={() => { setModal(null); setSel(new Set()); onReload?.(); }} /></Modal>}
    </div>
  );
}
