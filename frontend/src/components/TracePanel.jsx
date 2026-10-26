import React, { useContext, useState } from "react";
import { api, fmt, fmtDate } from "../api.js";
import { Ctx } from "../context.js";
import { Chip, Delta, Modal, Refs, Who, useAsync } from "./ui.jsx";
import { AdjustForm, AskForm, AttachForm, NoteForm, VerifyForm } from "./forms.jsx";

/** The trace drawer: where a number came from, how it was built, what depends on it, and everything done to it. */
export default function TracePanel({ lineKey, onClose }) {
  const { tick, openRef, can, refreshOverview } = useContext(Ctx);
  const { data: l, error, reload } = useAsync(() => api.line(lineKey), [lineKey, tick]);
  const [modal, setModal] = useState(null);
  if (error) return <div className="drawer-body"><div className="banner bad">{error.message}</div><button className="btn" onClick={onClose}>Close</button></div>;
  if (!l) return <div className="empty">Tracing…</div>;
  const cents = false;
  const done = () => { setModal(null); reload(); refreshOverview(); };

  return (
    <div>
      <div className="drawer-head">
        <div className="flex between">
          <div className="muted small mono">{l.form} line {l.line} · {l.jurisdiction} · {l.area.replace(/_/g, " ")}</div>
          <button className="btn small" onClick={onClose}>Close</button>
        </div>
        <div className="flex between" style={{ marginTop: 4 }}>
          <strong style={{ fontSize: 15 }}>{l.label}</strong>
        </div>
        <div className="flex wrap" style={{ marginTop: 6 }}>
          <span style={{ fontSize: 22, fontWeight: 700 }} className="num">{fmt(l.value, { cents })}</span>
          {l.adjusted && <Chip tone="purple" title={`engine ${fmt(l.engine_value, { cents })}`}>adjusted from {fmt(l.engine_value, { cents })}</Chip>}
          {l.pending_adjustments.length > 0 && <Chip tone="warn">{l.pending_adjustments.length} awaiting partner</Chip>}
          {l.verified ? <Chip tone="ok">verified ×{l.verifications.length}</Chip> : <Chip tone="ghost">unverified</Chip>}
          {l.open_notes > 0 && <Chip tone="bad">{l.open_notes} open note</Chip>}
          <Delta variance={l.variance} />
        </div>
        <div className="pill-row" style={{ marginTop: 8 }}>
          {can("adjust") && <button className="btn small primary" onClick={() => setModal("adjust")}>Adjust</button>}
          {can("verify") && <button className="btn small" onClick={() => setModal("verify")}>Verify</button>}
          {can("note") && <button className="btn small" onClick={() => setModal("note")}>Note</button>}
          {can("question_client") && <button className="btn small" onClick={() => setModal("ask")}>Ask</button>}
          {can("attach") && <button className="btn small" onClick={() => setModal("attach")}>Attach</button>}
        </div>
      </div>
      <div className="drawer-body">
        {l.note && <div className="banner info"><b>Engine note:</b> {l.note}</div>}
        {l.pending_adjustments.map((a) => <PendingAdjustment key={a.id} a={a} cents={cents} onDone={done} />)}

        <section>
          <h3>Sources · exact field on the document</h3>
          {l.sources_resolved.length === 0 && <div className="muted small">No direct sources: this line is built from other lines (see below).</div>}
          <table className="dense"><tbody>
            {l.sources_resolved.map((s) => (
              <tr key={s.ref} className="clickable" onClick={() => openRef(s.ref)}>
                <td><Chip>{(s.kind || "ref").replace(/_/g, " ")}</Chip></td>
                <td>{s.label}{s.kind === "extracted_value" && <div className="muted small">{s.document_id} page {s.page} · field "{s.data.field}" · read "{s.data.text_as_read}"</div>}</td>
                <td className="num">{s.value !== undefined ? fmt(s.value) : ""}{s.confidence !== undefined && <div className={`small ${s.confidence < 0.7 ? "delta up" : "muted"}`}>conf {s.confidence.toFixed(2)}</div>}</td>
              </tr>
            ))}
          </tbody></table>
        </section>

        <section>
          <h3>How it was built · rule {l.rule}</h3>
          <div className="muted small" style={{ marginBottom: 6 }}>{l.rule_text}</div>
          <div className="tree"><Tree node={l.upstream} openRef={openRef} root /></div>
        </section>

        <section>
          <h3>Where it flows · {l.downstream.length} dependent lines</h3>
          <div className="pill-row">{l.downstream.slice(0, 30).map((d) => <a key={d.key} className="reflink" onClick={() => openRef(d.key)} title={d.label}>{d.key} = {fmt(d.value)}</a>)}{l.downstream.length > 30 && <span className="muted small">+{l.downstream.length - 30} more</span>}</div>
        </section>

        <section>
          <h3>History · versions and last year</h3>
          <table className="dense"><tbody>
            {l.history.map((h) => <tr key={h.version}><td>{h.version}</td><td className="muted small">{fmtDate(h.computed_at)} {h.trigger ? `· ${h.trigger.slice(0, 70)}` : ""}</td><td className="num">{fmt(h.value, { cents })}</td></tr>)}
            {l.adjustment && <tr><td>working</td><td className="muted small">{fmtDate(l.adjustment.at)} · <Who id={l.adjustment.actor} /> · {l.adjustment.reason}</td><td className="num">{fmt(l.adjustment.new_value, { cents })}</td></tr>}
          </tbody></table>
        </section>

        {l.related.length > 0 && <section><h3>Related · across the return, years, related returns</h3>
          <ul style={{ margin: 0, paddingLeft: 16 }}>{l.related.map((r, i) => <li key={i}><Chip>{r.kind.replace("_", " ")}</Chip> <a className="reflink" onClick={() => openRef(r.ref)}>{r.label}</a></li>)}</ul></section>}

        <section>
          <h3>Verifications</h3>
          {l.verifications.length === 0 && <div className="muted small">None recorded.</div>}
          {l.verifications.map((v) => <div key={v.id} className="small"><Chip tone="ok">{v.type.replace(/_/g, " ")}</Chip> <Who id={v.actor} /> · {fmtDate(v.at)} {v.note && <span className="muted">· {v.note}</span>}</div>)}
        </section>

        <section>
          <h3>Adjustments</h3>
          {Object.values(l.adjustment ? [l.adjustment] : []).map((a) => <AdjRow key={a.id} a={a} cents={cents} />)}
          {!l.adjustment && l.pending_adjustments.length === 0 && <div className="muted small">The engine value stands.</div>}
        </section>

        <section>
          <h3>Notes, questions, attachments</h3>
          {l.notes.map((n) => <NoteRow key={n.id} n={n} onDone={done} />)}
          {l.questions.map((q) => <div key={q.id} className="card tight small"><Chip tone={q.status === "answered" ? "ok" : "warn"}>question → {q.to === "client" ? "client" : <Who id={q.to} />}</Chip> {q.text}{q.answer && <div className="thread"><b>Answer</b> (<Who id={q.answered_by} /> {fmtDate(q.answered_at)}): {q.answer} <Chip tone="ok">evidence</Chip></div>}</div>)}
          {l.attachments.map((a) => <div key={a.id} className="small"><Chip>attachment</Chip> <a href={`/api/attachments/${a.storage_key}`} target="_blank" rel="noreferrer">{a.name}</a> <span className="muted">{a.description}</span></div>)}
          {l.notes.length + l.questions.length + l.attachments.length === 0 && <div className="muted small">Nothing yet.</div>}
        </section>
      </div>

      {modal === "adjust" && <Modal title={`Adjust ${l.key}`} onClose={() => setModal(null)}><AdjustForm line={l} onDone={done} /></Modal>}
      {modal === "verify" && <Modal title={`Verify ${l.key}`} onClose={() => setModal(null)}><VerifyForm target={l.key} onDone={done} /></Modal>}
      {modal === "note" && <Modal title={`Note on ${l.key}`} onClose={() => setModal(null)}><NoteForm target={l.key} onDone={done} /></Modal>}
      {modal === "ask" && <Modal title={`Ask about ${l.key}`} onClose={() => setModal(null)}><AskForm target={l.key} onDone={done} /></Modal>}
      {modal === "attach" && <Modal title={`Attach evidence to ${l.key}`} onClose={() => setModal(null)}><AttachForm target={l.key} onDone={done} /></Modal>}
    </div>
  );
}

function Tree({ node, openRef, root }) {
  const l = node.line;
  return (
    <div className={root ? "" : "node"}>
      <div className="row" onClick={() => !root && openRef(node.key)}>
        <span><span className="mono muted">{node.key}</span> {l ? l.label.slice(0, 60) : "(not in this version)"}</span>
        <span className="num">{l ? fmt(l.value, {}) : ""}</span>
      </div>
      {node.sources?.map((s) => <div className="leaf" key={s.ref}><a onClick={() => openRef(s.ref)}>↳ {s.label?.slice(0, 70) || s.ref}{s.value !== undefined ? ` = ${fmt(s.value)}` : ""}</a></div>)}
      {node.inputs?.map((c) => <Tree key={c.key} node={c} openRef={openRef} />)}
    </div>
  );
}

export function AdjRow({ a, cents }) {
  return (
    <div className="card tight small">
      <div className="flex between"><span><Chip tone={a.status === "applied" ? "purple" : a.status === "proposed" ? "warn" : "bad"}>{a.status}</Chip> <Who id={a.actor} /> · {fmtDate(a.at)}</span><span className="num">{fmt(a.old_value, { cents })} → <b>{fmt(a.new_value, { cents })}</b></span></div>
      <div><b>Why:</b> {a.reason} {a.authority && <span className="muted">· authority: {a.authority}</span>}</div>
      <div className="muted">Tax effect: federal {fmt(a.tax_effect?.federal)} · California {fmt(a.tax_effect?.california)} ({a.tax_effect?.category} rate){a.requires_partner ? " · requires partner sign-off" : ""}{a.layer === "amendment" ? " · amendment layer" : ""}</div>
      {a.evidence?.length > 0 && <Refs refs={a.evidence} />}
      {a.approved_by && <div className="muted">Approved by <Who id={a.approved_by} /> {fmtDate(a.approved_at)}</div>}
    </div>
  );
}

function PendingAdjustment({ a, cents, onDone }) {
  const { can, toast } = useContext(Ctx);
  async function act(approve) {
    try { await api.approve({ adjustment_id: a.id, approve, reason: approve ? null : "Rejected by partner" }); toast(approve ? "Adjustment approved and applied" : "Adjustment rejected"); onDone(); } catch (e) { toast(e.message, true); }
  }
  return (
    <div className="banner warn">
      <div><b>Awaiting partner approval</b> · <Who id={a.actor} /> proposed {fmt(a.old_value, { cents })} → <b>{fmt(a.new_value, { cents })}</b> (effect fed {fmt(a.tax_effect?.federal)} / CA {fmt(a.tax_effect?.california)})</div>
      <div className="small">{a.reason}</div>
      {can("approve_adjustment") && <div className="pill-row" style={{ marginTop: 6 }}><button className="btn small primary" onClick={() => act(true)}>Approve</button><button className="btn small danger" onClick={() => act(false)}>Reject</button></div>}
    </div>
  );
}

export function NoteRow({ n, onDone }) {
  const { can, toast } = useContext(Ctx);
  const [reply, setReply] = useState("");
  async function act(action, text) {
    try { await api.noteAct({ note_id: n.id, action, text }); onDone?.(); setReply(""); } catch (e) { toast(e.message, true); }
  }
  const tone = n.status === "resolved" ? "ok" : n.blocking ? "bad" : n.kind === "judgment" || n.kind === "election" ? "purple" : "warn";
  return (
    <div className="card tight small">
      <div className="flex between wrap">
        <span><Chip tone={tone}>{n.blocking && n.status === "open" ? "BLOCKS FILING · " : ""}{n.kind}{n.status === "resolved" ? " · resolved" : ""}</Chip> <Who id={n.actor} /> · {fmtDate(n.at)}{n.assigned_to && <> · assigned to <Who id={n.assigned_to} /></>}{n.due && <> · due {n.due}</>}</span>
        {can("note") && <span className="pill-row">{n.status === "open" ? <button className="btn small" onClick={() => act("resolve", reply || "Resolved")}>Resolve</button> : <button className="btn small" onClick={() => act("reopen", reply || "Reopened")}>Reopen</button>}</span>}
      </div>
      <div style={{ marginTop: 4 }}>{n.text}</div>
      {n.authority && <div className="muted">Authority: {n.authority}</div>}
      {n.alternatives && <div className="muted">Alternatives considered: {n.alternatives}</div>}
      {n.thread?.length > 0 && <div className="thread">{n.thread.map((t, i) => <div key={i}><b>{t.kind}</b> <Who id={t.actor} /> {fmtDate(t.at)}: {t.text}</div>)}</div>}
      {can("note") && <div className="flex" style={{ marginTop: 6 }}><input className="grow" placeholder="Reply or resolution…" value={reply} onChange={(e) => setReply(e.target.value)} /><button className="btn small" disabled={!reply} onClick={() => act("reply", reply)}>Reply</button></div>}
    </div>
  );
}
