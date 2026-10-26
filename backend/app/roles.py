"""Roles, actors and permissions.

Actors are firm staff (firm.staff), client users (firm.client_users), plus two
synthetic read-only actors: the next-year preparer view and an IRS examiner.
Permissions are enforced server-side on every mutating route.
"""
from __future__ import annotations

from typing import Any

from .packet import Packet

ROLE_LABELS = {
    "preparer": "Preparer",
    "reviewer": "Reviewer",
    "partner": "Partner",
    "firm_administrator": "Firm administrator",
    "quality_reviewer": "Quality reviewer",
    "client": "Client",
    "examiner": "IRS examiner (read-only record)",
}

# capability -> roles allowed
CAPABILITIES: dict[str, set[str]] = {
    "adjust": {"preparer", "reviewer", "partner"},
    "approve_adjustment": {"partner"},
    "verify": {"preparer", "reviewer", "partner"},
    "note": {"preparer", "reviewer", "partner", "quality_reviewer"},
    "block": {"reviewer", "partner"},                 # blocking review notes
    "question_client": {"preparer", "reviewer", "partner"},
    "answer_client_question": {"client"},
    "attach": {"preparer", "reviewer", "partner", "client"},
    "signoff_preparer": {"preparer"},
    "signoff_reviewer": {"reviewer", "partner"},
    "signoff_partner": {"partner"},
    "assign": {"firm_administrator", "partner", "reviewer"},
    "standards": {"firm_administrator"},
    "view_logs": {"firm_administrator", "partner"},
    "time": {"preparer", "reviewer", "partner"},
    "filing": {"partner", "reviewer"},                 # send to client, e-file, record outcomes
    "client_approve": {"client"},
    "undo": {"preparer", "reviewer", "partner", "firm_administrator"},
    "check_override": {"reviewer", "partner"},
    "whatif": {"preparer", "reviewer", "partner"},
    "carryforward": {"preparer", "reviewer", "partner"},
}


def actors(packet: Packet) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in packet.firm["staff"]:
        out.append({
            "id": s["id"], "name": s["name"], "role": s["role"], "role_label": ROLE_LABELS.get(s["role"], s["role"]),
            "credential": s.get("credential"), "clearance": bool(s.get("sensitive_data_clearance")),
            "active_from": s.get("active_from"), "note": s.get("note"), "kind": "staff",
        })
    for c in packet.firm.get("client_users", []):
        out.append({"id": c["id"], "name": c["name"], "role": "client", "role_label": "Client", "clearance": True, "kind": "client"})
    out.append({"id": "examiner", "name": "IRS examiner", "role": "examiner", "role_label": ROLE_LABELS["examiner"], "clearance": True, "kind": "external",
                "note": "Sees the frozen filed record and its evidence. Cannot change anything."})
    for a in out:
        a["capabilities"] = capabilities_for(a["role"])
    return out


def capabilities_for(role: str) -> list[str]:
    return sorted(cap for cap, allowed in CAPABILITIES.items() if role in allowed)


def actor(packet: Packet, actor_id: str) -> dict[str, Any] | None:
    return next((a for a in actors(packet) if a["id"] == actor_id), None)


def can(a: dict[str, Any] | None, capability: str) -> bool:
    if not a:
        return False
    return a["role"] in CAPABILITIES.get(capability, set())


def mask_sensitive(value: str | None, kind: str) -> str | None:
    if value is None:
        return None
    s = str(value)
    if kind == "ssn":
        return "***-**-" + s[-4:]
    if kind in ("account_number", "routing"):
        return "****" + s[-4:]
    if kind == "ip_pin":
        return "******"
    if kind == "ein":
        return "**-***" + s[-4:]
    return "****"
