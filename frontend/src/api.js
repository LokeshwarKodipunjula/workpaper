// Thin API client. The actor header is how the role switcher works: every request
// carries who is acting, and the server enforces what that role may do.
const BASE = import.meta.env.VITE_API_BASE || "";

let currentActor = localStorage.getItem("wp.actor") || "";
export function setActor(id) {
  currentActor = id;
  try { localStorage.setItem("wp.actor", id); } catch {}
}
export function getActor() { return currentActor; }

async function req(method, path, body, isForm) {
  const headers = { "X-Actor": currentActor };
  if (!isForm) headers["Content-Type"] = "application/json";
  const res = await fetch(BASE + path, { method, headers, body: isForm ? body : body ? JSON.stringify(body) : undefined });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch {}
    const err = new Error(msg); err.status = res.status; throw err;
  }
  return res.json();
}

export const api = {
  heartbeat: () => req("GET", "/api/heartbeat"),
  meta: () => req("GET", "/api/meta"),
  overview: (v) => req("GET", `/api/overview${v ? `?version=${v}` : ""}`),
  lines: (params = {}) => req("GET", "/api/lines?" + new URLSearchParams(params)),
  line: (key, v) => req("GET", `/api/lines/${encodeURIComponent(key)}${v ? `?version=${v}` : ""}`),
  documents: (v) => req("GET", `/api/documents${v ? `?version=${v}` : ""}`),
  document: (id, v) => req("GET", `/api/documents/${id}${v ? `?version=${v}` : ""}`),
  ref: (r) => req("GET", `/api/ref?r=${encodeURIComponent(r)}`),
  search: (q) => req("GET", `/api/search?q=${encodeURIComponent(q)}`),
  checks: (params = {}) => req("GET", "/api/checks?" + new URLSearchParams(params)),
  activity: (sinceMe) => req("GET", `/api/activity${sinceMe ? "?since_me=true" : ""}`),
  compare: (a, b) => req("GET", `/api/versions/compare?a=${a}&b=${b}`),
  records: () => req("GET", "/api/records"),
  record: (name, v) => req("GET", `/api/records/${name}${v ? `?version=${v}` : ""}`),
  household: () => req("GET", "/api/household"),
  firm: () => req("GET", "/api/firm"),
  timeline: () => req("GET", "/api/timeline"),
  client: () => req("GET", "/api/client"),

  adjust: (b) => req("POST", "/api/adjustments", b),
  adjustBulk: (items) => req("POST", "/api/adjustments/bulk", { items }),
  approve: (b) => req("POST", "/api/adjustments/approve", b),
  verify: (b) => req("POST", "/api/verifications", b),
  verifyBulk: (b) => req("POST", "/api/verifications/bulk", b),
  note: (b) => req("POST", "/api/notes", b),
  noteAct: (b) => req("POST", "/api/notes/act", b),
  ask: (b) => req("POST", "/api/questions", b),
  answer: (b) => req("POST", "/api/questions/answer", b),
  attach: (form) => req("POST", "/api/attachments", form, true),
  signoff: (b) => req("POST", "/api/signoffs", b),
  assign: (b) => req("POST", "/api/assignments", b),
  time: (b) => req("POST", "/api/time", b),
  standards: (b) => req("POST", "/api/standards", b),
  filing: (b) => req("POST", "/api/filing", b),
  clientApprove: (b) => req("POST", "/api/client/approve", b),
  readMarker: () => req("POST", "/api/read-marker"),
  override: (b) => req("POST", "/api/checks/override", b),
  whatif: (b, save) => req("POST", `/api/whatif${save ? "?save=true" : ""}`, b),
  undo: (b) => req("POST", "/api/undo", b),
  carry: (b) => req("POST", "/api/carryforward", b),
  reset: () => req("POST", "/api/admin/reset"),
  seed: () => req("POST", "/api/admin/seed"),
};

export function fmt(v, opts = {}) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "number") {
    if (opts.cents) v = v / 100;
    const neg = v < 0;
    const s = Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: opts.cents || Math.abs(v) % 1 ? 2 : 0 });
    return neg ? `(${s})` : s;
  }
  return String(v);
}

export function fmtDate(s) {
  if (!s) return "";
  return s.slice(0, 10);
}

export function wsUrl(actor, view) {
  const base = BASE || window.location.origin;
  const u = new URL(base);
  u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
  u.pathname = "/ws";
  u.search = `?actor=${encodeURIComponent(actor)}&view=${encodeURIComponent(view || "")}`;
  return u.toString();
}
