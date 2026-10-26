import React, { useContext, useEffect, useMemo, useState } from "react";
import { api, fmt, fmtDate } from "../api.js";
import { Ctx } from "../context.js";
import { Chip, Modal, Who, useAsync } from "./ui.jsx";
import { AttachForm, NoteForm, VerifyForm } from "./forms.jsx";
import { NoteRow } from "./TracePanel.jsx";

/**
 * Simulated source document. The packet has no page images, so each page is rendered from
 * printed_content with the extracted values highlighted both in the text and at their synthetic
 * positions. A real page image would replace the paper div; the highlight boxes and the
 * value -> line links stay exactly as they are.
 */
export default function DocumentViewer({ docId, page: initialPage, focusEv, onClose }) {
  const { tick, openRef, can, refreshOverview } = useContext(Ctx);
  const { data, error, reload } = useAsync(() => api.document(docId), [docId, tick]);
  const [page, setPage] = useState(initialPage || 1);
  const [active, setActive] = useState(focusEv || null);
  const [modal, setModal] = useState(null);
  useEffect(() => { if (focusEv && data) { const e = data.landed.values.find((v) => v.ev.id === focusEv); if (e) setPage(e.ev.page); } }, [focusEv, data]);
  if (error) return <div className="drawer-body"><div className="banner bad">{error.message}</div></div>;
  if (!data) return <div className="empty">Opening document…</div>;
  const d = data.document;
  const pg = d.pages.find((p) => p.page === page) || d.pages[0];
  const values = data.landed.values.filter((v) => v.ev.page === pg?.page);
  const unreadPages = new Set(((d.extraction.reason || "").match(/[Pp]age (\d+)/g) || []).map((m) => +m.replace(/\D/g, "")));
  const done = () => { setModal(null); reload(); refreshOverview(); };

  return (
    <div>
      <div className="drawer-head">
        <div className="flex between"><div className="muted small mono">{d.id} · {d.document_type} · {d.belongs_to} · received {fmtDate(d.received_at)} by {d.uploaded_by}{d.marked_corrected ? " · CORRECTED" : ""}</div><button className="btn small" onClick={onClose}>Close</button></div>
        <strong style={{ fontSize: 15 }}>{d.title}</strong>
        <div className="flex wrap" style={{ marginTop: 6 }}>
          <Chip tone={d.extraction.status === "extracted" ? "ok" : d.extraction.status === "partial" ? "bad" : ""}>{d.extraction.status}</Chip>
          {data.landed.superseded && <Chip tone="bad">superseded</Chip>}
          {!data.landed.used_by_engine && !data.landed.superseded && <Chip tone="warn">not used by {data.landed.version}</Chip>}
          <Chip>{data.landed.values_landed}/{data.landed.values_total} values landed on {data.landed.lines.length} lines</Chip>
          {data.landed.first_used_in && <Chip tone="ghost">first used in {data.landed.first_used_in}</Chip>}
          {data.verifications.length > 0 && <Chip tone="ok">verified</Chip>}
        </div>
        {data.landed.why_not && <div className="banner warn small" style={{ marginTop: 6 }}>{data.landed.why_not}</div>}
        <div className="pill-row" style={{ marginTop: 8 }}>
          {can("verify") && <button className="btn small" onClick={() => setModal("verify")}>Verify document</button>}
          {can("note") && <button className="btn small" onClick={() => setModal("note")}>Note</button>}
          {can("attach") && <button className="btn small" onClick={() => setModal("attach")}>Attach</button>}
        </div>
      </div>
      <div className="drawer-body">
        <div className="pagebar">{d.pages.map((p) => <button key={p.page} className={`btn small ${p.page === pg.page ? "active" : ""} ${unreadPages.has(p.page) ? "unread" : ""}`} onClick={() => setPage(p.page)} title={unreadPages.has(p.page) ? "not read by the pipeline" : ""}>p{p.page}</button>)}</div>
        {unreadPages.has(pg.page) && <div className="banner bad small">The pipeline did not read this page. Nothing on it reached the return. Enter what matters as an adjustment with <code>doc:{d.id}#page{pg.page}</code> as evidence.</div>}
        <Paper content={pg.printed_content} values={values} active={active} setActive={setActive} />
        <section>
          <h3>Values read from page {pg.page} · click to see where each landed</h3>
          {values.length === 0 && <div className="muted small">No values extracted from this page.</div>}
          <table className="dense"><thead><tr><th>Field</th><th className="right">Value</th><th>Read as</th><th>Conf</th><th>Landed on</th></tr></thead><tbody>
            {values.map(({ ev, lines }) => (
              <tr key={ev.id} className={`clickable ${active === ev.id ? "selected" : ""}`} onClick={() => setActive(ev.id)}>
                <td><div>{ev.label}</div><div className="muted small mono">{ev.id} · {ev.field}</div></td>
                <td className="num">{fmt(ev.value)}</td>
                <td className="mono small">{ev.text_as_read || <span className="muted">blank</span>}</td>
                <td className={ev.confidence < 0.7 ? "delta up" : ev.confidence < 0.9 ? "delta flat" : "muted"}>{ev.confidence.toFixed(2)}</td>
                <td>{lines.length ? <div className="pill-row">{lines.map((k) => <a key={k} className="reflink" onClick={(e) => { e.stopPropagation(); openRef(k); }}>{k}</a>)}</div> : <span className="muted small">nowhere</span>}</td>
              </tr>
            ))}
          </tbody></table>
        </section>
        {data.related_documents.length > 0 && <section><h3>Related documents</h3><div className="pill-row">{data.related_documents.map((r) => <a key={r} className="reflink" onClick={() => openRef(r)}>{r}</a>)}</div></section>}
        {data.timeline.length > 0 && <section><h3>Timeline</h3>{data.timeline.map((t) => <div key={t.id} className="small"><span className="muted">{fmtDate(t.at)}</span> {t.event.replace(/_/g, " ")} {t.detail}</div>)}</section>}
        <section><h3>Verifications & notes</h3>
          {data.verifications.map((v) => <div key={v.id} className="small"><Chip tone="ok">{v.type.replace(/_/g, " ")}</Chip> <Who id={v.actor} /> {fmtDate(v.at)} {v.note}</div>)}
          {data.notes.map((n) => <NoteRow key={n.id} n={n} onDone={done} />)}
          {data.attachments.map((a) => <div key={a.id} className="small"><Chip>attachment</Chip> <a href={`/api/attachments/${a.storage_key}`} target="_blank" rel="noreferrer">{a.name}</a> {a.description}</div>)}
        </section>
      </div>
      {modal === "verify" && <Modal title={`Verify ${d.id}`} onClose={() => setModal(null)}><VerifyForm target={d.id} onDone={done} /></Modal>}
      {modal === "note" && <Modal title={`Note on ${d.id}`} onClose={() => setModal(null)}><NoteForm target={d.id} onDone={done} /></Modal>}
      {modal === "attach" && <Modal title={`Attach to ${d.id}`} onClose={() => setModal(null)}><AttachForm target={d.id} onDone={done} /></Modal>}
    </div>
  );
}

function Paper({ content, values, active, setActive }) {
  // highlight text_as_read occurrences inside the printed content; place position boxes over the "page".
  const segments = useMemo(() => {
    const marks = [];
    for (const { ev } of values) {
      const t = ev.text_as_read;
      if (!t) continue;
      let idx = content.indexOf(t);
      // disambiguate repeated strings by also matching the label nearby when possible
      if (idx >= 0) marks.push({ start: idx, end: idx + t.length, id: ev.id });
    }
    marks.sort((a, b) => a.start - b.start);
    const out = []; let pos = 0;
    for (const m of marks) { if (m.start < pos) continue; out.push({ text: content.slice(pos, m.start) }); out.push({ text: content.slice(m.start, m.end), id: m.id }); pos = m.end; }
    out.push({ text: content.slice(pos) });
    return out;
  }, [content, values]);
  return (
    <div className="stack">
      <div className="page-wrap">
        <div className="page-paper">{segments.map((s, i) => s.id ? <mark key={i} className={active === s.id ? "active" : ""} onClick={() => setActive(s.id)}>{s.text}</mark> : <span key={i}>{s.text}</span>)}</div>
      </div>
      {values.some(({ ev }) => ev.position) && (
        <div>
          <div className="muted small" style={{ marginBottom: 4 }}>Page map: where each value sits on the page (synthetic positions; a real page image drops in here with the same highlight boxes).</div>
          <div className="page-map">
            {values.map(({ ev }) => ev.position && (
              <div key={ev.id} className={`hl ${active === ev.id ? "active" : ""} ${ev.confidence < 0.7 ? "low" : ""}`} title={`${ev.label}: ${ev.text_as_read} (conf ${ev.confidence})`}
                style={{ left: `${ev.position.x0 * 100}%`, top: `${ev.position.y0 * 100}%`, width: `${Math.max(4, (ev.position.x1 - ev.position.x0) * 100)}%`, height: `${Math.max(2.2, (ev.position.y1 - ev.position.y0) * 100)}%` }}
                onClick={() => setActive(ev.id)}><span>{ev.field}</span></div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
