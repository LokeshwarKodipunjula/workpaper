import React, { useContext, useMemo, useState } from "react";
import { api, fmtDate } from "../api.js";
import { Ctx } from "../context.js";
import { Chip, Loading, useAsync } from "../components/ui.jsx";

export default function Documents() {
  const { tick, openRef } = useContext(Ctx);
  const { data, error } = useAsync(() => api.documents(), [tick]);
  const [filter, setFilter] = useState("all");
  const [who, setWho] = useState("all");
  const rows = useMemo(() => {
    if (!data) return [];
    return data.filter((d) => {
      if (who !== "all" && d.belongs_to !== who) return false;
      if (filter === "unused") return !d.used_by_engine && !d.superseded;
      if (filter === "reference") return d.why_not && d.why_not.includes("reference");
      if (filter === "problems") return d.extraction_status !== "extracted" || d.low_confidence_values > 0 || d.marked_corrected || d.received_after_version;
      if (filter === "late") return d.received_at > "2026-03-02T22:15:00Z";
      if (filter === "unverified") return !d.verified;
      return true;
    });
  }, [data, filter, who]);
  if (!data) return <Loading error={error} />;
  const counts = { used: data.filter((d) => d.used_by_engine).length, unused: data.filter((d) => !d.used_by_engine && !d.superseded).length, superseded: data.filter((d) => d.superseded).length, not_extracted: data.filter((d) => d.extraction_status === "not_extracted").length };
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div><h1>Document index</h1><div className="muted">{data.length} documents · {counts.used} used by the engine · {counts.unused} received but not used · {counts.superseded} superseded · {counts.not_extracted} not extracted (reproduced as structured records). Every document is accounted for: either its values landed on lines, or the index says why not.</div></div>
      <div className="toolbar">
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All</option><option value="unused">Not used by the current version</option><option value="reference">Reference only (no line cites it)</option><option value="problems">Problems: partial, corrected, low confidence, late</option><option value="late">Arrived after "upload complete"</option><option value="unverified">Not yet verified</option>
        </select>
        <select value={who} onChange={(e) => setWho(e.target.value)}>
          <option value="all">Everyone</option><option value="taxpayer">Ngozi</option><option value="spouse">Erik</option><option value="joint">Joint</option><option value="dependent:ada">Ada</option><option value="dependent:theo">Theo</option>
        </select>
        <span className="muted small">{rows.length} shown</span>
      </div>
      <div className="card">
        <table className="dense">
          <thead><tr><th>Doc</th><th>Title</th><th>Type</th><th>Of</th><th>Received</th><th>Extraction</th><th className="right">Landed</th><th>Where</th><th>Flags</th></tr></thead>
          <tbody>
            {rows.map((d) => (
              <tr key={d.id} className="clickable" onClick={() => openRef(d.id)}>
                <td className="key">{d.id}</td>
                <td>{d.title}{d.why_not && <div className="muted small">{d.why_not}</div>}</td>
                <td className="small">{d.document_type}</td>
                <td className="small">{d.belongs_to.replace("dependent:", "")}</td>
                <td className="small nowrap">{fmtDate(d.received_at)}<div className="muted">{d.uploaded_by}{d.first_used_in ? ` · ${d.first_used_in}` : ""}</div></td>
                <td><Chip tone={d.extraction_status === "extracted" ? "ok" : d.extraction_status === "partial" ? "bad" : ""}>{d.extraction_status}</Chip></td>
                <td className="num">{d.values_landed}/{d.values_total}</td>
                <td className="small muted">{d.lines.slice(0, 4).join(", ")}{d.lines.length > 4 ? ` +${d.lines.length - 4}` : ""}</td>
                <td><span className="pill-row">
                  {d.marked_corrected && <Chip tone="warn">corrected</Chip>}{d.superseded && <Chip tone="bad">superseded</Chip>}
                  {!d.used_by_engine && !d.superseded && d.extraction_status !== "not_extracted" && <Chip tone="warn">not used</Chip>}
                  {d.low_confidence_values > 0 && <Chip tone="warn">{d.low_confidence_values} low-conf</Chip>}
                  {d.open_notes > 0 && <Chip tone="bad">{d.open_notes} note</Chip>}
                  {d.verified && <Chip tone="ok">verified</Chip>}
                </span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
