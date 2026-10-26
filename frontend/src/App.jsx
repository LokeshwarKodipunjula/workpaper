import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api, getActor, setActor, wsUrl } from "./api.js";
import { Ctx } from "./context.js";
import { Chip, STATUS_TONE } from "./components/ui.jsx";
import TracePanel from "./components/TracePanel.jsx";
import DocumentViewer from "./components/DocumentViewer.jsx";
import Overview from "./pages/Overview.jsx";
import AreaPage from "./pages/Area.jsx";
import Documents from "./pages/Documents.jsx";
import Checks from "./pages/Checks.jsx";
import Records from "./pages/Records.jsx";
import Activity from "./pages/Activity.jsx";
import Versions from "./pages/Versions.jsx";
import Filing from "./pages/Filing.jsx";
import Firm from "./pages/Firm.jsx";
import ClientView from "./pages/ClientView.jsx";
import WhatIf from "./pages/WhatIf.jsx";
import Household from "./pages/Household.jsx";

export default function App() {
  const [meta, setMeta] = useState(null);
  const [actorId, setActorId] = useState(getActor());
  const [drawer, setDrawer] = useState(null); // {kind:'line'|'document'|'ref', id, ...}
  const [presence, setPresence] = useState([]);
  const [toast, setToast] = useState(null);
  const [tick, setTick] = useState(0); // bumps on every live event -> pages refetch
  const [overview, setOverview] = useState(null);
  const [lastEvent, setLastEvent] = useState(null);
  const wsRef = useRef(null);
  const loc = useLocation();
  const nav = useNavigate();

  useEffect(() => { api.meta().then(setMeta).catch((e) => showToast(e.message, true)); }, []);

  const actor = useMemo(() => meta?.actors.find((a) => a.id === actorId) || null, [meta, actorId]);

  function showToast(msg, err) { setToast({ msg, err }); setTimeout(() => setToast(null), 3800); }

  const refreshOverview = useCallback(() => {
    if (!actorId) return;
    api.overview().then(setOverview).catch(() => {});
  }, [actorId]);
  useEffect(refreshOverview, [refreshOverview, tick]);

  // live updates: WebSocket when the host allows it, otherwise poll the event sequence.
  // Serverless hosts (Vercel) refuse the upgrade, so the first failed connection switches to polling.
  useEffect(() => {
    if (!actorId) return;
    let ws; let closed = false; let opened = false; let poll = null; let lastSeq = null;
    function startPolling() {
      if (poll) return;
      setPresence([]);
      const check = async () => {
        try {
          const h = await api.heartbeat();
          if (lastSeq !== null && h.seq !== lastSeq) setTick((t) => t + 1);
          lastSeq = h.seq;
        } catch { /* backend unreachable; try again next round */ }
      };
      check();
      poll = setInterval(check, 3000);
    }
    function connect() {
      try { ws = new WebSocket(wsUrl(actorId, loc.pathname)); } catch { startPolling(); return; }
      wsRef.current = ws;
      ws.onopen = () => { opened = true; };
      ws.onmessage = (m) => {
        const d = JSON.parse(m.data);
        if (d.type === "presence") setPresence(d.presence);
        else { setTick((t) => t + 1); if (d.type === "event") setLastEvent(d.event); if (d.type === "reset") showToast("Workpaper reset"); }
      };
      ws.onclose = () => {
        if (closed) return;
        if (opened) setTimeout(connect, 1500);   // the server went away; it will come back
        else startPolling();                      // never connected: this host has no WebSockets
      };
    }
    connect();
    return () => { closed = true; ws?.close(); if (poll) clearInterval(poll); };
  }, [actorId]);
  useEffect(() => { try { wsRef.current?.send(JSON.stringify({ type: "view", view: loc.pathname })); } catch {} }, [loc.pathname]);

  function pickActor(id) { setActor(id); setActorId(id); setDrawer(null); const a = meta?.actors.find((x) => x.id === id); if (a?.role === "client") nav("/client"); else if (a?.role === "examiner") nav("/filing"); else if (loc.pathname === "/client") nav("/"); }

  const openRef = useCallback((r) => {
    if (!r) return;
    if (/^D\d\d$/.test(r)) return setDrawer({ kind: "document", id: r });
    if (r.startsWith("doc:")) { const m = r.match(/^doc:(D\d\d)#page(\d+)$/); return setDrawer({ kind: "document", id: m[1], page: +m[2] }); }
    if (r.startsWith("ev-")) return setDrawer({ kind: "ev", id: r });
    if (/^(F\d{4}|Sch|FTB|ScheduleS)/.test(r)) return setDrawer({ kind: "line", id: r });
    return setDrawer({ kind: "ref", id: r });
  }, []);

  // What this actor may do comes from the server with the actor list (roles.py is the only
  // copy of the matrix). The UI uses it to hide buttons; the API enforces it regardless.
  const can = useCallback((cap) => !!actor && actor.capabilities.includes(cap), [actor]);

  const ctx = { meta, actor, actorId, overview, refreshOverview, openRef, setDrawer, drawer, tick, toast: showToast, can, presence, lastEvent };

  if (!meta) return <div className="empty">Loading workpaper…</div>;
  if (!actorId || !actor) return <Ctx.Provider value={ctx}><RolePicker meta={meta} onPick={pickActor} /></Ctx.Provider>;

  const isClient = actor.role === "client";
  const isExaminer = actor.role === "examiner";
  return (
    <Ctx.Provider value={ctx}>
      <div className="shell">
        <TopBar meta={meta} actor={actor} onPick={pickActor} presence={presence} overview={overview} />
        <div className={`body ${drawer ? "with-drawer" : ""}`}>
          <nav className="sidenav">
            {!isClient && <>
              <NavLink to="/" end>Overview {overview && <Chip tone={overview.checks.fail ? "bad" : overview.checks.warn ? "warn" : "ok"}>{overview.checks.fail || overview.checks.warn}</Chip>}</NavLink>
              <div className="section">Areas</div>
              {meta.areas.map((a) => {
                const s = overview?.areas.find((x) => x.id === a.id);
                return <NavLink key={a.id} to={`/area/${a.id}`}>{a.title}{s && <span className={`dot ${STATUS_TONE[s.status] || "info"}`} title={s.status} />}</NavLink>;
              })}
              <div className="section">Evidence</div>
              <NavLink to="/documents">Documents</NavLink>
              <NavLink to="/household">Household & people</NavLink>
              <NavLink to="/checks">Checks {overview && <Chip tone={overview.checks.fail ? "bad" : "warn"}>{overview.checks.fail} / {overview.checks.warn}</Chip>}</NavLink>
              <div className="section">Review</div>
              <NavLink to="/records">Records</NavLink>
              <NavLink to="/versions">Versions & compare</NavLink>
              <NavLink to="/whatif">What-if</NavLink>
              <NavLink to="/activity">Activity {overview?.since_you_looked ? <Chip tone="accent">{overview.since_you_looked} new</Chip> : null}</NavLink>
              <NavLink to="/filing">Filing & after</NavLink>
              {!isExaminer && <><div className="section">Firm</div><NavLink to="/firm">Standards, people, time</NavLink></>}
            </>}
            {isClient && <>
              <NavLink to="/client">Your return</NavLink>
              <NavLink to="/documents">Your documents</NavLink>
            </>}
          </nav>
          <main className="main">
            <Routes>
              <Route path="/" element={isClient ? <ClientView /> : <Overview />} />
              <Route path="/area/:id" element={<AreaPage />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/household" element={<Household />} />
              <Route path="/checks" element={<Checks />} />
              <Route path="/records" element={<Records />} />
              <Route path="/records/:name" element={<Records />} />
              <Route path="/activity" element={<Activity />} />
              <Route path="/versions" element={<Versions />} />
              <Route path="/filing" element={<Filing />} />
              <Route path="/firm" element={<Firm />} />
              <Route path="/client" element={<ClientView />} />
              <Route path="/whatif" element={<WhatIf />} />
            </Routes>
          </main>
          {drawer && (
            <aside className="drawer">
              {drawer.kind === "line" && <TracePanel key={drawer.id} lineKey={drawer.id} onClose={() => setDrawer(null)} />}
              {drawer.kind === "document" && <DocumentViewer key={drawer.id + (drawer.page || "")} docId={drawer.id} page={drawer.page} focusEv={drawer.ev} onClose={() => setDrawer(null)} />}
              {drawer.kind === "ev" && <EvRedirect id={drawer.id} />}
              {drawer.kind === "ref" && <RefPanel r={drawer.id} onClose={() => setDrawer(null)} />}
            </aside>
          )}
        </div>
        {toast && <div className={`toast ${toast.err ? "err" : ""}`}>{toast.msg}</div>}
      </div>
    </Ctx.Provider>
  );
}

function EvRedirect({ id }) {
  const { setDrawer } = React.useContext(Ctx);
  useEffect(() => { api.ref(id).then((n) => setDrawer({ kind: "document", id: n.document_id, page: n.page, ev: id })); }, [id]);
  return <div className="empty">Opening source…</div>;
}

function RefPanel({ r, onClose }) {
  const [node, setNode] = useState(null);
  useEffect(() => { api.ref(r).then(setNode); }, [r]);
  return (
    <div>
      <div className="drawer-head flex between"><div><div className="muted small">{node?.kind}</div><strong>{node?.label || r}</strong></div><button className="btn small" onClick={onClose}>Close</button></div>
      <div className="drawer-body">
        <RefBody node={node} />
      </div>
    </div>
  );
}

export function RefBody({ node }) {
  if (!node) return <div className="empty">Loading…</div>;
  const d = node.data;
  if (node.kind === "client_answer") return <div className="card tight"><div className="muted small">Questionnaire {node.ref} · answered by {d.answered_by} {d.answered_at?.slice(0, 10)}</div><p><strong>Q:</strong> {d.question}</p><p><strong>A:</strong> {String(d.answer)}</p></div>;
  if (node.kind === "client_message") return <div className="card tight"><div className="muted small">{d.from} → {d.to} · {d.sent_at?.slice(0, 16)}</div><p>{d.text}</p></div>;
  if (node.kind === "call_note") return <div className="card tight"><div className="muted small">Call {d.date?.slice(0, 10)} · {d.participants?.join(", ")}</div><ul>{d.notes.map((n, i) => <li key={i}>{n}</li>)}</ul></div>;
  if (node.kind === "timeline_event") return <div className="card tight"><div className="muted small">{d.at}</div><p><strong>{d.event}</strong> {d.detail}</p></div>;
  if (node.kind === "person") return <div className="card tight"><dl className="kv">{Object.entries(d).map(([k, v]) => <React.Fragment key={k}><dt>{k}</dt><dd>{String(v)}</dd></React.Fragment>)}</dl></div>;
  return <pre className="card tight" style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(d, null, 2)}</pre>;
}

function RolePicker({ meta, onPick }) {
  return (
    <div style={{ maxWidth: 760, margin: "60px auto" }} className="stack">
      <div><h1>Miraflores Workpaper</h1><p className="muted">{meta.packet.name} · client {meta.packet.client_id}. Pick who you are. Every action is recorded under this identity and every role sees only what it may.</p></div>
      <div className="grid2">
        {meta.actors.map((a) => (
          <button key={a.id} className="card" style={{ textAlign: "left", cursor: "pointer" }} onClick={() => onPick(a.id)}>
            <div className="flex between"><strong>{a.name}</strong><Chip tone={a.kind === "staff" ? "accent" : a.kind === "client" ? "ok" : ""}>{a.role_label}</Chip></div>
            <div className="muted small" style={{ marginTop: 4 }}>{a.credential ? `${a.credential} · ` : ""}{a.clearance ? "sensitive data clearance" : "no clearance: identifiers masked, views logged"}{a.note ? ` · ${a.note}` : ""}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

function TopBar({ meta, actor, onPick, presence, overview }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState(null);
  const { openRef } = React.useContext(Ctx);
  const nav = useNavigate();
  useEffect(() => {
    if (!q.trim()) { setHits(null); return; }
    const t = setTimeout(() => api.search(q).then(setHits).catch(() => setHits([])), 200);
    return () => clearTimeout(t);
  }, [q]);
  function go(h) {
    setQ(""); setHits(null);
    if (h.kind === "note" || h.kind === "question") { if (h.target) openRef(h.target); else nav("/activity"); return; }
    openRef(h.ref);
  }
  const ws = overview?.summary?.working_summary;
  return (
    <header className="topbar">
      <div className="brand">Miraflores<span>Okafor-Lindqvist · 2025 · MFJ · CA→TX</span></div>
      <div style={{ position: "relative" }}>
        <input placeholder="Search a number, line, document or answer…" value={q} onChange={(e) => setQ(e.target.value)} />
        {hits && <div className="search-pop">{hits.length === 0 && <div className="hit muted">No matches</div>}{hits.map((h, i) => <div className="hit" key={i} onClick={() => go(h)}><Chip>{h.kind.replace("_", " ")}</Chip><span className="grow">{h.label}</span>{h.value !== undefined && <span className="num mono">{typeof h.value === "number" ? h.value.toLocaleString() : h.value}</span>}</div>)}</div>}
      </div>
      <div className="grow" />
      {ws && actor.role !== "client" && <div className="small" style={{ color: "#c9d4ff" }}>Fed {ws.federal.balance_due_working >= 0 ? "owe" : "refund"} <b>{Math.abs(ws.federal.balance_due_working).toLocaleString()}</b> · CA {ws.california.balance_due_working >= 0 ? "owe" : "refund"} <b>{Math.abs(ws.california.balance_due_working).toLocaleString()}</b> · <span className="muted">{meta.latest_version}{overview?.filing?.status !== "open" ? ` · ${overview.filing.status.replace(/_/g, " ")}` : ""}</span></div>}
      <div className="presence" title={presence.map((p) => `${p.name} (${p.role}) ${p.view}`).join("\n")}>
        {presence.slice(0, 6).map((p, i) => <span key={i} className={`avatar ${p.actor === actor.id ? "me" : ""}`} title={`${p.name} · ${p.view}`}>{p.name.split(" ").map((x) => x[0]).join("").slice(0, 2)}</span>)}
      </div>
      <select value={actor.id} onChange={(e) => onPick(e.target.value)} title="Role switcher">
        {meta.actors.map((a) => <option key={a.id} value={a.id}>{a.name} · {a.role_label}</option>)}
      </select>
    </header>
  );
}
