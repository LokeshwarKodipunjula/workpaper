import React, { useContext, useState } from "react";
import { api, fmt } from "../api.js";
import { Ctx } from "../context.js";
import { Chip, Loading, Who, useAsync } from "../components/ui.jsx";

/** What the client sees: plain-language summary, questions to answer (answers become evidence), approval and e-signature. */
export default function ClientView() {
  const { tick, actor, toast, refreshOverview } = useContext(Ctx);
  const { data, error, reload } = useAsync(() => api.client(), [tick]);
  const [answers, setAnswers] = useState({});
  const [pin, setPin] = useState("");
  const [comment, setComment] = useState("");
  if (!data) return <Loading error={error} />;
  const ws = data.summary.working_summary;
  const open = data.questions.filter((q) => q.status === "open");
  const isClient = actor.role === "client";
  async function send(q) {
    try { await api.answer({ question_id: q.id, answer: answers[q.id] }); toast("Thank you. Your answer is now part of the record."); setAnswers({ ...answers, [q.id]: "" }); reload(); refreshOverview(); } catch (e) { toast(e.message, true); }
  }
  async function approve(ok) {
    try { await api.clientApprove({ approved: ok, pin, comment }); toast(ok ? "Signed. Your preparer can now e-file." : "Sent back to your preparer."); reload(); refreshOverview(); } catch (e) { toast(e.message, true); }
  }
  const owe = (v) => (v >= 0 ? <>you owe <b>{fmt(v)}</b></> : <>refund of <b>{fmt(-v)}</b></>);
  return (
    <div className="stack" style={{ gap: 14, maxWidth: 920 }}>
      <div><h1>Your 2025 return</h1><div className="muted">Ngozi Okafor & Erik Lindqvist · filing jointly · California part-year, Texas from July 15. Prepared by Miraflores.</div></div>
      <div className="grid2">
        <div className="stat"><div className="label">Federal</div><div className="value">{owe(ws.federal.balance_due_working)}</div><div className="sub">total tax {fmt(ws.federal.total_tax_working)} · paid in {fmt(ws.federal.payments)} (includes the 36,000 extension payment)</div></div>
        <div className="stat"><div className="label">California</div><div className="value">{owe(ws.california.balance_due_working)}</div><div className="sub">total tax {fmt(ws.california.total_tax_working)} · paid in {fmt(ws.california.payments)}</div></div>
      </div>

      <div className="card">
        <h2>Questions from your preparer {open.length > 0 && <Chip tone="warn">{open.length} waiting</Chip>}</h2>
        {data.questions.length === 0 && <div className="muted small">No questions right now.</div>}
        {data.questions.map((q) => (
          <div key={q.id} className="card tight" style={{ marginBottom: 8 }}>
            <div className="small muted"><Who id={q.actor} /> asked {q.at.slice(0, 10)}{q.due ? ` · needed by ${q.due}` : ""}</div>
            <div style={{ margin: "4px 0" }}>{q.text}</div>
            {q.status === "answered" ? <div className="thread"><b>You answered</b> {q.answered_at?.slice(0, 10)}: {q.answer}</div>
              : isClient ? <div className="flex"><input className="grow" placeholder="Your answer…" value={answers[q.id] || ""} onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })} /><button className="btn primary small" disabled={!answers[q.id]} onClick={() => send(q)}>Send</button></div>
                : <Chip tone="warn">awaiting client</Chip>}
          </div>
        ))}
      </div>

      <div className="card">
        <h2>Approval & e-file signature (Form 8879 / FTB 8879)</h2>
        {data.filing.status === "sent_to_client" ? (
          isClient ? <div className="form">
            <div className="banner info">Please review the amounts above. Signing authorizes Miraflores to e-file your federal and California returns with these figures. If anything changes afterwards, this signature is voided and you will be asked again.</div>
            <div className="grid2"><label className="field">Your 5-digit PIN<input value={pin} onChange={(e) => setPin(e.target.value)} maxLength={5} /></label><label className="field">Comment (optional)<input value={comment} onChange={(e) => setComment(e.target.value)} /></label></div>
            <div className="pill-row"><button className="btn primary" disabled={pin.length !== 5} onClick={() => approve(true)}>I approve and sign</button><button className="btn" onClick={() => approve(false)}>Send back with questions</button></div>
          </div> : <div className="muted small">Awaiting the client's signature.</div>
        ) : data.approvals.length > 0 && data.approvals[data.approvals.length - 1].approved && data.approvals[data.approvals.length - 1].fingerprint === data.fingerprint ? <div className="banner ok">Signed {data.approvals[data.approvals.length - 1].at.slice(0, 10)}. The return has not changed since.</div>
          : data.approvals.length > 0 ? <div className="banner warn">Your earlier signature no longer matches the current return (it changed afterwards). Your preparer will send it again.</div>
            : <div className="muted small">Your preparer will send the return here when it is ready for your approval. Status: {data.filing.status.replace(/_/g, " ")}.</div>}
      </div>

      <details className="card"><summary>Your organizer answers and messages (what we relied on)</summary>
        <table className="dense" style={{ marginTop: 8 }}><tbody>{data.questionnaire.map((q) => <tr key={q.id}><td className="key">{q.id}</td><td className="small">{q.question}</td><td className="small">{String(q.answer)}</td></tr>)}</tbody></table>
        {data.messages.map((m) => <div key={m.id} className="small" style={{ marginTop: 4 }}><span className="muted mono">{m.sent_at.slice(0, 10)}</span> <b>{m.from}</b>: {m.text}</div>)}
      </details>
    </div>
  );
}
