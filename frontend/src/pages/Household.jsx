import React, { useContext } from "react";
import { api } from "../api.js";
import { Ctx } from "../context.js";
import { Chip, Loading, Ref, useAsync } from "../components/ui.jsx";

export default function Household() {
  const { tick, actor } = useContext(Ctx);
  const { data, error } = useAsync(() => api.household(), [tick]);
  if (!data) return <Loading error={error} />;
  const h = data.household;
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div><h1>Household & people</h1><div className="muted">Exactly as the client entered them in the organizer ({h.entered_by}). {actor.clearance ? "You have sensitive-data clearance: this view is logged." : "Identifiers are masked for your role."}</div></div>
      <div className="card">
        <h2>People</h2>
        <table className="dense"><thead><tr><th>Name</th><th>Role</th><th>SSN</th><th>DOB</th><th>Notes</th><th>Identity evidence</th></tr></thead><tbody>
          {h.people.map((p) => <tr key={p.id}><td><b>{p.name}</b></td><td>{p.role}{p.relationship ? ` · ${p.relationship}` : ""}</td><td className="mono">{p.ssn}</td><td className="mono">{p.dob}</td><td className="small">{p.occupation}{p.full_time_student ? " · full-time student" : ""}{p.note ? ` · ${p.note}` : ""}{p.own_income ? ` · ${p.own_income}` : ""}{p.ip_pin ? ` · IP PIN on file` : ""}</td>
            <td className="pill-row">{p.id === "ngozi" && <><Ref r="D04" /><Ref r="D03" /></>}{p.id === "erik" && <Ref r="D05" />}{p.id === "theo" && <><Ref r="D71" /><Chip tone="bad">SSN differs from organizer: see checks</Chip></>}{p.id === "ada" && <Ref r="D59" />}</td></tr>)}
        </tbody></table>
      </div>
      <div className="grid2">
        <div className="card"><h2>Addresses & residency</h2>
          {h.addresses.map((a, i) => <div key={i} className="small" style={{ padding: "3px 0" }}><span className="mono muted">{a.from} → {a.to || "present"}</span> {a.address} <span className="muted">({a.type})</span></div>)}
          <div style={{ marginTop: 8 }}>{h.residency.map((r, i) => <Chip key={i} tone={r.state === "CA" ? "warn" : "ok"}>{r.state} {r.status} {r.from} → {r.to}</Chip>)}</div>
        </div>
        <div className="card"><h2>Refund / payment account & e-signature</h2>
          <dl className="kv"><dt>Bank</dt><dd>{h.bank_account_for_refund_or_payment.bank}</dd><dt>Routing</dt><dd className="mono">{h.bank_account_for_refund_or_payment.routing}</dd><dt>Account</dt><dd className="mono">{h.bank_account_for_refund_or_payment.account} ({h.bank_account_for_refund_or_payment.type})</dd><dt>Prior-year AGI for e-sign</dt><dd className="mono">{h.prior_year_agi_for_esignature} <Ref r="py:/return_2024/lines/F1040.11" label="2024 return" /></dd></dl>
        </div>
      </div>
      <div className="card"><h2>Related returns</h2>
        <table className="dense"><thead><tr><th>Who</th><th>Return</th><th>Prepared by</th><th>In this packet</th></tr></thead><tbody>
          {data.related_returns.map((r, i) => <tr key={i}><td>{r.who}</td><td>{r.return}</td><td>{r.prepared_by}</td><td className="small">{String(r.in_this_packet)}</td></tr>)}
        </tbody></table>
      </div>
    </div>
  );
}
