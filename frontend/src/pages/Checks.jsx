import React, { useContext, useMemo, useState } from "react";
import { api } from "../api.js";
import { Ctx } from "../context.js";
import { Chip, Loading, Modal, Refs, Who, useAsync } from "../components/ui.jsx";

export function CheckRow({ c, onDone }) {
  const { can, toast } = useContext(Ctx);
  const [modal, setModal] = useState(false);
  const [reason, setReason] = useState("");
  const [status, setStatus] = useState("accepted");
  const tone = { fail: "bad", warn: "warn", info: "", pass: "ok", accepted: "ok", waived: "" }[c.status] || "";
  async function submit(e) {
    e.preventDefault();
    try { await api.override({ check_id: c.id, status, reason }); toast(`Check ${status}`); setModal(false); onDone?.(); } catch (err) { toast(err.message, true); }
  }
  return (
    <div className="check-row">
      <div><Chip tone={tone}>{c.status}</Chip><div className="muted small" style={{ marginTop: 4 }}>{c.area.replace(/_/g, " ")}</div></div>
      <div>
        <div><b>{c.title}</b></div>
        <div className="small" style={{ margin: "2px 0 4px" }}>{c.message}</div>
        {c.action && c.status !== "pass" && <div className="small muted">→ {c.action}</div>}
        <Refs refs={c.refs} />
        {c.override && <div className="small muted" style={{ marginTop: 4 }}>{c.override.status} by <Who id={c.override.actor} />: {c.override.reason}</div>}
      </div>
      <div>{can("check_override") && ["fail", "warn", "info"].includes(c.status) && <button className="btn small" onClick={() => setModal(true)}>Resolve</button>}</div>
      {modal && <Modal title="Resolve check" onClose={() => setModal(false)}>
        <form className="form" onSubmit={submit}>
          <div className="small">{c.title}</div>
          <label className="field">Outcome<select value={status} onChange={(e) => setStatus(e.target.value)}><option value="accepted">Accepted: reviewed and the return is right as is</option><option value="waived">Waived: not applicable / out of scope</option></select></label>
          <label className="field">Reason (recorded with your name)<textarea value={reason} onChange={(e) => setReason(e.target.value)} /></label>
          <button className="btn primary" disabled={!reason}>Record</button>
        </form>
      </Modal>}
    </div>
  );
}

export default function Checks() {
  const { tick, meta } = useContext(Ctx);
  const { data, error, reload } = useAsync(() => api.checks(), [tick]);
  const [status, setStatus] = useState("open");
  const [area, setArea] = useState("all");
  const [q, setQ] = useState("");
  const rows = useMemo(() => (data || []).filter((c) => {
    if (status === "open" && !["fail", "warn"].includes(c.status)) return false;
    if (status !== "open" && status !== "all" && c.status !== status) return false;
    if (area !== "all" && c.area !== area) return false;
    if (q && !`${c.title} ${c.message} ${c.id}`.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  }), [data, status, area, q]);
  if (!data) return <Loading error={error} />;
  const n = (s) => data.filter((c) => c.status === s).length;
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div><h1>Checks that don't trust the engine</h1><div className="muted">Every check re-derives something from the documents, the client's answers, prior years or agency records and compares it with what the engine produced. {n("fail")} failing · {n("warn")} warnings · {n("info")} informational · {n("pass")} passing · {n("accepted") + n("waived")} resolved.</div></div>
      <div className="toolbar">
        <select value={status} onChange={(e) => setStatus(e.target.value)}><option value="open">Failing + warnings</option><option value="fail">Failing</option><option value="warn">Warnings</option><option value="info">Informational</option><option value="pass">Passing</option><option value="accepted">Accepted</option><option value="waived">Waived</option><option value="all">All</option></select>
        <select value={area} onChange={(e) => setArea(e.target.value)}><option value="all">All areas</option>{meta.areas.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}</select>
        <input placeholder="filter…" value={q} onChange={(e) => setQ(e.target.value)} />
        <span className="muted small">{rows.length} shown</span>
      </div>
      <div className="stack">{rows.map((c) => <CheckRow key={c.id} c={c} onDone={reload} />)}{rows.length === 0 && <div className="empty">Nothing here.</div>}</div>
    </div>
  );
}
