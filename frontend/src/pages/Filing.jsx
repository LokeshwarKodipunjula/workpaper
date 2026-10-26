import React, { useContext, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmt, fmtDate } from "../api.js";
import { Ctx } from "../context.js";
import { Chip, Loading, Ref, Refs, Who, useAsync } from "../components/ui.jsx";

const STEPS = ["open", "in_review", "partner_approved", "sent_to_client", "client_approved", "efiled", "accepted"];
const LABELS = { open: "Preparing", in_review: "In review", partner_approved: "Partner approved", sent_to_client: "With client", client_approved: "Client signed 8879", extension_filed: "Extension filed", efiled: "E-filed", rejected: "Rejected", accepted: "Accepted · frozen", amending: "Amending", amended_filed: "Amended return filed" };

export default function Filing() {
  const { overview, tick, can, toast, refreshOverview, actor } = useContext(Ctx);
  const tl = useAsync(() => api.timeline(), [tick]);
  const [detail, setDetail] = useState("");
  const status = overview?.filing?.status || "open";
  const idx = STEPS.indexOf(status);
  async function set(s, d) {
    try { await api.filing({ status: s, detail: d || detail || null }); toast(`Filing status: ${LABELS[s] || s}`); setDetail(""); refreshOverview(); } catch (e) { toast(e.message, true); }
  }
  async function signReturn() {
    try { await api.signoff({ scope: "return", level: "partner" }); toast("Partner sign-off on the whole return recorded. It reopens automatically if any line changes."); refreshOverview(); } catch (e) { toast(e.message, true); }
  }
  async function decide(adj, approve) {
    try { await api.approve({ adjustment_id: adj.id, approve }); toast(`${adj.line_key} ${approve ? "approved" : "rejected"}`); refreshOverview(); } catch (e) { toast(e.message, true); }
  }
  if (!overview || !tl.data) return <Loading error={tl.error} />;
  const pending = overview.pending_adjustments || [];
  const returnSignoffs = overview.signoffs.filter((s) => s.scope === "return");
  const frozen = ["accepted", "amended_filed"].includes(status);
  const agency = tl.data.agency;
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div><h1>Filing & after</h1><div className="muted">Extensions, client approval and e-signature, e-file and rejections, freeze at filing, amend on top, notices years later.</div></div>
      <div className="stepper">{STEPS.map((s, i) => <div key={s} className={`step ${i < idx ? "done" : ""} ${s === status ? "current" : ""}`}>{LABELS[s]}</div>)}{["rejected", "amending", "amended_filed", "extension_filed"].includes(status) && <div className="step current">{LABELS[status]}</div>}</div>

      {frozen && <div className="banner ok"><b>The filed return is frozen.</b> Nothing on it can change. To correct it, open an amendment: changes then go on an amendment layer on top of the filed record, and the filed record stays exactly as filed.</div>}
      {status === "sent_to_client" && <div className="banner info">Waiting for the client. If anything on the return changes now, the client's approval is voided automatically and they must approve again.</div>}
      {status === "rejected" && <div className="banner bad">E-file rejected. Fix the cause (see the error below), then re-transmit. The client's signature stays valid only if the amounts are unchanged.</div>}

      <div className="grid2">
        <div className="card">
          <h2>Actions · {actor.role_label}</h2>
          <div className="small muted" style={{ marginBottom: 8 }}>Gates: partner sign-off on the whole return before it goes to the client; no open blocking notes; client approval and 8879 before e-file; the return must be unchanged since the client signed.</div>
          <label className="field">Detail (optional)<input value={detail} onChange={(e) => setDetail(e.target.value)} placeholder="submission id, rejection code, note" /></label>
          <div className="pill-row" style={{ marginTop: 8 }}>
            {can("signoff_partner") && !frozen && <button className="btn" onClick={signReturn}>Partner sign-off on the whole return</button>}
            {can("filing") && !frozen && <>
              <button className="btn" onClick={() => set("in_review")}>Hand off to review</button>
              <button className="btn" onClick={() => set("extension_filed", detail || "Form 4868 with 36,000; FTB 3519 with 0 (estimated from v2).")}>Record extension</button>
              <button className="btn primary" onClick={() => set("sent_to_client")}>Send to client for approval</button>
              <button className="btn primary" onClick={() => set("efiled")}>Transmit e-file</button>
              <button className="btn danger" onClick={() => set("rejected", detail || "R0000-504-02: dependent TIN/name control mismatch (dependent 2).")}>Record rejection</button>
              <button className="btn" onClick={() => set("accepted", detail || "Federal and California accepted.")}>Record acceptance (freeze)</button>
            </>}
            {can("filing") && frozen && <button className="btn primary" onClick={() => set("amending", "Amendment opened on top of the filed record.")}>Open amendment</button>}
            {can("filing") && status === "amending" && <button className="btn" onClick={() => set("amended_filed")}>Record amended return filed (freeze)</button>}
            {actor.role === "client" && <Link className="btn primary" to="/client">Review and sign</Link>}
            {!can("filing") && actor.role !== "client" && <span className="muted small">Your role cannot change filing status.</span>}
          </div>
          {pending.length > 0 && <div style={{ marginTop: 10 }}>
            <h3>Awaiting partner approval · {pending.length}</h3>
            <div className="muted small">Adjustments over the firm's tax-effect threshold are proposed, not applied, until a partner decides. The whole-return sign-off is refused while any remain.</div>
            {pending.map((x) => <div key={x.id} className="small" style={{ display: "flex", gap: 8, alignItems: "center", padding: "4px 0", borderBottom: "1px solid var(--line)" }}>
              <Ref r={x.line_key} /><span style={{ flex: 1 }}>{fmt(x.old_value)} → <b>{fmt(x.new_value)}</b> · {x.reason}</span>
              <span className="muted mono">fed {fmt(x.tax_effect?.federal)} · CA {fmt(x.tax_effect?.california)}</span>
              {can("approve_adjustment") && <><button className="btn small primary" onClick={() => decide(x, true)}>Approve</button><button className="btn small" onClick={() => decide(x, false)}>Reject</button></>}
            </div>)}
          </div>}
          {returnSignoffs.length > 0 && <div className="pill-row small" style={{ marginTop: 8 }}>Whole-return sign-off: {returnSignoffs.map((s) => <Chip key={s.id} tone={s.status === "active" ? "ok" : "warn"} title={`${s.actor} ${fmtDate(s.at)}${s.reopened_cause ? " · " + s.reopened_cause : ""}`}>{s.level} {s.status === "active" ? "✓" : "reopened"}</Chip>)}</div>}
          <h3 style={{ marginTop: 14 }}>History</h3>
          {overview.filing.history.length === 0 && <div className="muted small">No filing events yet.</div>}
          {overview.filing.history.map((h) => <div key={h.id} className="small"><span className="muted mono">{h.at.slice(0, 16)}</span> <Chip tone="accent">{LABELS[h.status] || h.status}</Chip> <Who id={h.actor} /> {h.detail}</div>)}
          {overview.client_approvals.map((c) => <div key={c.id} className="small"><span className="muted mono">{c.at.slice(0, 16)}</span> <Chip tone={c.approved ? "ok" : "bad"}>client {c.approved ? "approved" : "declined"}</Chip> fed owe {fmt(c.amounts?.federal_balance_due)} · CA {fmt(c.amounts?.california_balance_due)} <span className="muted mono">#{c.fingerprint}</span></div>)}
        </div>
        <div className="card">
          <h2>Agency record</h2>
          <h3>E-file submissions</h3>
          {agency.efile.map((e, i) => <div key={i} className="small" style={{ padding: "3px 0" }}><Chip tone={e.status === "accepted" ? "ok" : e.status === "rejected" ? "bad" : ""}>{e.jurisdiction} {e.status}</Chip> {fmtDate(e.date)} <span className="mono muted">{e.submission_id}</span>{e.errors?.map((x, j) => <div key={j} className="delta up">{x.code}: {x.message} {x.code === "R0000-504-02" && <> → <Ref r="D71" label="Theo's SSN card" /> vs <Ref r="household:theo" label="organizer entry" /></>}</div>)}</div>)}
          <h3 style={{ marginTop: 10 }}>Notices</h3>
          {agency.notices.map((n) => <div key={n.id} className="small" style={{ padding: "3px 0" }}><b>{n.agency} {n.type}</b> · TY {n.tax_year} · {n.dated} <Ref r={n.document} /><div className="muted">{n.summary || n.items_under_examination?.join(" · ")} {n.status || ""}</div>{n.items_under_examination && <Link to="/records/notice_response" className="btn small" style={{ marginTop: 4 }}>Open the self-contained response record</Link>}</div>)}
          <h3 style={{ marginTop: 10 }}>Post-filing interest & penalty</h3>
          <PostFiling rates={tl.data.post_filing_rates} summary={overview.summary.working_summary} />
        </div>
      </div>

      <div className="card">
        <h2>Season timeline (packet) · replay</h2>
        <table className="dense"><tbody>{tl.data.packet_timeline.map((t) => <tr key={t.id}><td className="mono small nowrap">{t.at.slice(0, 16).replace("T", " ")}</td><td><b>{t.event.replace(/_/g, " ")}</b>{t.actor && <> · <Who id={t.actor} /></>}</td><td className="small">{t.detail}</td><td><Refs refs={t.refs || []} /></td></tr>)}</tbody></table>
      </div>
    </div>
  );
}

function PostFiling({ rates, summary }) {
  const due = summary.federal.balance_due_working;
  const extensionPaid = 36000;
  const months = 3; // 2026-04-15 -> 2026-07-20 as in the timeline
  const underpaid = Math.max(0, due);
  const ftp = underpaid * rates.irs_failure_to_pay_penalty_per_month * Math.ceil(months);
  const interest = underpaid * rates.irs_underpayment_interest_rate_annual * (96 / 365);
  return <div className="small">If the working federal balance of <b>{fmt(due)}</b> is paid 2026-07-20 (96 days after 2026-04-15): failure-to-pay ≈ <b>{fmt(Math.round(ftp))}</b> ({rates.irs_failure_to_pay_penalty_per_month * 100}% × {Math.ceil(months)} months) and interest ≈ <b>{fmt(Math.round(interest))}</b> ({rates.irs_underpayment_interest_rate_annual * 100}%/yr). The extension payment of {fmt(extensionPaid)} was credited 2026-04-14. {rates.note}</div>;
}
