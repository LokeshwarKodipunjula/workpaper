import React, { useContext, useEffect, useState } from "react";
import { api, fmt } from "../api.js";
import { Ctx } from "../context.js";

const CATEGORIES = ["wages", "interest", "schc_profit", "stcg", "ltcg", "ordinary_income", "adjustment", "salt", "itemized", "ca_source_income"];

export function AdjustForm({ line, onDone }) {
  const { toast } = useContext(Ctx);
  const cents = false;
  const [v, setV] = useState(cents ? (line.value / 100).toString() : String(line.value));
  const [reason, setReason] = useState("");
  const [authority, setAuthority] = useState("");
  const [category, setCategory] = useState(line.category);
  const [evidence, setEvidence] = useState((line.sources || []).slice(0, 3).join(", "));
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const n = parseFloat(v);
    if (isNaN(n)) return setPreview(null);
    api.whatif({ name: "preview", adjustments: [{ line_key: line.key, new_value: cents ? Math.round(n * 100) : n, category }] }).then(setPreview).catch(() => {});
  }, [v, category, line.key, cents]);
  async function submit(e) {
    e.preventDefault(); setBusy(true);
    try {
      const n = parseFloat(v);
      const r = await api.adjust({ line_key: line.key, new_value: isNaN(n) ? v : cents ? Math.round(n * 100) : n, reason, authority: authority || null, category, evidence: evidence.split(",").map((s) => s.trim()).filter(Boolean) });
      const st = r.event.payload.status;
      toast(st === "proposed" ? "Adjustment proposed: tax effect over the threshold, routed to the partner." : `Adjustment applied${r.reopened.length ? `; ${r.reopened.length} sign-off(s) reopened` : ""}.`);
      onDone();
    } catch (err) { toast(err.message, true); } finally { setBusy(false); }
  }
  const eff = preview?.rows?.[0]?.effect;
  return (
    <form className="form" onSubmit={submit}>
      <div className="muted small">Engine value {fmt(line.engine_value, { cents })}{line.adjusted ? ` · currently ${fmt(line.value, { cents })}` : ""}. The original is never lost: this appends a change with who, why and tax effect.</div>
      <label className="field">New value<input autoFocus value={v} onChange={(e) => setV(e.target.value)} /></label>
      <label className="field">Why (required)<textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="What the document says / what the client confirmed / what the engine did wrong" /></label>
      <div className="grid2">
        <label className="field">Authority relied on<input value={authority} onChange={(e) => setAuthority(e.target.value)} placeholder="e.g. msg-08, IRC §170(f)(12), Pub 526" /></label>
        <label className="field">Tax-effect category<select value={category} onChange={(e) => setCategory(e.target.value)}>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select></label>
      </div>
      <label className="field">Evidence refs (comma separated)<input value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder="ev-1049, D64, msg-08, doc:D31#page32" /></label>
      {eff && <div className={`banner ${eff.requires_partner ? "warn" : "info"}`}>Estimated effect: federal <b>{fmt(eff.federal)}</b> · California <b>{fmt(eff.california)}</b> ({eff.category} rate){eff.requires_partner ? " · over 1,000: needs partner sign-off before it applies" : ""}</div>}
      <div className="flex"><button className="btn primary" disabled={busy || !reason}>Record adjustment</button></div>
    </form>
  );
}

export function VerifyForm({ target, onDone, targets }) {
  const { toast } = useContext(Ctx);
  const [type, setType] = useState("agreed_to_source_document");
  const [note, setNote] = useState("");
  const [types, setTypes] = useState(["agreed_to_source_document", "recalculated", "confirmed_with_client", "agreed_to_prior_year", "agreed_to_third_party_record"]);
  useEffect(() => { api.firm().then((f) => f.standards?.verification_types && setTypes(f.standards.verification_types)).catch(() => {}); }, []);
  async function submit(e) {
    e.preventDefault();
    try {
      if (targets) { await api.verifyBulk({ targets, type, note }); toast(`${targets.length} items verified (one undo reverses all).`); }
      else { await api.verify({ target, type, note }); toast("Verification recorded"); }
      onDone();
    } catch (err) { toast(err.message, true); }
  }
  return (
    <form className="form" onSubmit={submit}>
      <label className="field">How was it verified?<select value={type} onChange={(e) => setType(e.target.value)}>{types.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}</select></label>
      <label className="field">Note<textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="What you compared it to" /></label>
      <button className="btn primary">Record {targets ? `${targets.length} verifications` : "verification"}</button>
    </form>
  );
}

export function NoteForm({ target, area, onDone, defaultKind = "review" }) {
  const { toast, can, meta } = useContext(Ctx);
  const [kind, setKind] = useState(defaultKind);
  const [text, setText] = useState("");
  const [blocking, setBlocking] = useState(false);
  const [assigned, setAssigned] = useState("");
  const [due, setDue] = useState("");
  const [authority, setAuthority] = useState("");
  const [alternatives, setAlternatives] = useState("");
  async function submit(e) {
    e.preventDefault();
    try { await api.note({ target, area, text, kind, blocking, assigned_to: assigned || null, due: due || null, authority: authority || null, alternatives: alternatives || null }); toast("Note recorded"); onDone(); } catch (err) { toast(err.message, true); }
  }
  return (
    <form className="form" onSubmit={submit}>
      <div className="grid2">
        <label className="field">Kind<select value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="review">Review note</option><option value="judgment">Judgment call</option><option value="election">Election</option><option value="due_diligence">Due diligence</option><option value="penalty">Penalty decision</option><option value="variance">Variance explanation</option><option value="memo">Memo</option>
        </select></label>
        <label className="field">Assign to<select value={assigned} onChange={(e) => setAssigned(e.target.value)}><option value="">—</option>{meta.actors.filter((a) => a.kind === "staff").map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
      </div>
      <label className="field">Text<textarea autoFocus value={text} onChange={(e) => setText(e.target.value)} /></label>
      {(kind === "judgment" || kind === "election" || kind === "penalty" || kind === "due_diligence") && <>
        <label className="field">Authority relied on (required for judgment calls)<input value={authority} onChange={(e) => setAuthority(e.target.value)} placeholder="IRC / Reg / Pub / ruling / firm standard" /></label>
        <label className="field">Alternatives considered<input value={alternatives} onChange={(e) => setAlternatives(e.target.value)} /></label>
      </>}
      <div className="flex">
        <label className="field">Due<input type="date" value={due} onChange={(e) => setDue(e.target.value)} /></label>
        {can("block") && kind === "review" && <label className="flex small"><input type="checkbox" checked={blocking} onChange={(e) => setBlocking(e.target.checked)} /> Blocks filing until resolved</label>}
      </div>
      <button className="btn primary" disabled={!text}>Record</button>
    </form>
  );
}

export function AskForm({ target, area, onDone }) {
  const { toast, meta } = useContext(Ctx);
  const [to, setTo] = useState("client");
  const [text, setText] = useState("");
  const [due, setDue] = useState("");
  async function submit(e) {
    e.preventDefault();
    try { await api.ask({ to, text, target, area, due: due || null }); toast(to === "client" ? "Question sent to the client; the answer will become evidence." : "Question sent"); onDone(); } catch (err) { toast(err.message, true); }
  }
  return (
    <form className="form" onSubmit={submit}>
      <label className="field">To<select value={to} onChange={(e) => setTo(e.target.value)}><option value="client">Client (Ngozi & Erik)</option>{meta.actors.filter((a) => a.kind === "staff").map((a) => <option key={a.id} value={a.id}>{a.name} · {a.role_label}</option>)}</select></label>
      <label className="field">Question<textarea autoFocus value={text} onChange={(e) => setText(e.target.value)} /></label>
      <label className="field">Needed by<input type="date" value={due} onChange={(e) => setDue(e.target.value)} /></label>
      <button className="btn primary" disabled={!text}>Send</button>
    </form>
  );
}

export function AttachForm({ target, onDone }) {
  const { toast } = useContext(Ctx);
  const [file, setFile] = useState(null);
  const [desc, setDesc] = useState("");
  async function submit(e) {
    e.preventDefault();
    const fd = new FormData(); fd.append("target", target); fd.append("description", desc); fd.append("file", file);
    try { await api.attach(fd); toast("Attached as evidence"); onDone(); } catch (err) { toast(err.message, true); }
  }
  return (
    <form className="form" onSubmit={submit}>
      <input type="file" onChange={(e) => setFile(e.target.files[0])} />
      <label className="field">What it proves<input value={desc} onChange={(e) => setDesc(e.target.value)} /></label>
      <button className="btn primary" disabled={!file}>Attach</button>
    </form>
  );
}
