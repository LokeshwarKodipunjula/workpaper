import React, { useContext, useEffect, useRef, useState } from "react";
import { fmt } from "../api.js";
import { Ctx } from "../context.js";

export function Chip({ tone = "", children, title }) {
  return <span className={`chip ${tone}`} title={title}>{children}</span>;
}

export const STATUS_TONE = { blocked: "bad", open_items: "warn", in_progress: "", prepared: "accent", reviewed: "purple", signed: "ok", pass: "ok", fail: "bad", warn: "warn", info: "", accepted: "ok", waived: "" };
export const STATUS_LABEL = { blocked: "Blocked", open_items: "Open items", in_progress: "In progress", prepared: "Prepared", reviewed: "Reviewed", signed: "Signed off" };

export function Stat({ label, value, sub, delta }) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub && <div className="sub">{sub}</div>}
      {delta}
    </div>
  );
}

export function Delta({ variance }) {
  if (!variance) return <span className="muted small">—</span>;
  const cls = variance.delta > 0 ? "up" : variance.delta < 0 ? "down" : "flat";
  return (
    <span className={`delta ${cls} small`} title={`2024: ${fmt(variance.prior)}`}>
      {variance.delta > 0 ? "+" : ""}{fmt(variance.delta)} ({variance.pct > 0 ? "+" : ""}{variance.pct}%)
      {variance.flagged && <Chip tone="warn"> swing</Chip>}
    </span>
  );
}

/** Any README reference becomes a clickable link that opens the right thing in the drawer. */
export function Ref({ r, label, children }) {
  const { openRef } = useContext(Ctx);
  return <a className="reflink" onClick={(e) => { e.stopPropagation(); openRef(r); }} title={r}>{children || label || r}</a>;
}

export function Refs({ refs = [] }) {
  if (!refs.length) return null;
  return <div className="refs">{refs.slice(0, 24).map((r) => <Ref key={r} r={r} />)}{refs.length > 24 && <span className="muted small">+{refs.length - 24}</span>}</div>;
}

export function Modal({ title, onClose, children, width = 520 }) {
  useEffect(() => {
    const h = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(10,14,20,.45)", zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center" }} onClick={onClose}>
      <div className="card" style={{ width, maxHeight: "85vh", overflow: "auto" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex between" style={{ marginBottom: 10 }}><h2 style={{ margin: 0 }}>{title}</h2><button className="btn small" onClick={onClose}>Close</button></div>
        {children}
      </div>
    </div>
  );
}

export function useAsync(fn, deps) {
  const [state, set] = useState({ loading: true, data: null, error: null });
  const tick = useRef(0);
  const reload = () => {
    const my = ++tick.current;
    set((s) => ({ ...s, loading: true }));
    fn().then((data) => my === tick.current && set({ loading: false, data, error: null }))
      .catch((error) => my === tick.current && set({ loading: false, data: null, error }));
  };
  useEffect(reload, deps); // eslint-disable-line
  return { ...state, reload };
}

export function Loading({ error }) {
  if (error) return <div className="banner bad">{String(error.message || error)}</div>;
  return <div className="empty">Loading…</div>;
}

export function Bar({ value, max }) {
  const pct = max ? Math.min(100, (value / max) * 100) : 0;
  return <div className={`bar ${value > max ? "over" : ""}`}><div style={{ width: `${pct}%` }} /></div>;
}

export function Money({ v, cents }) {
  return <span className="num">{fmt(v, { cents })}</span>;
}

export function Who({ id }) {
  const { meta } = useContext(Ctx);
  const a = meta?.actors?.find((x) => x.id === id);
  if (id === "system") return <span className="muted">system</span>;
  return <span title={id}>{a ? a.name : id}</span>;
}

export function Empty({ children }) { return <div className="empty">{children}</div>; }
