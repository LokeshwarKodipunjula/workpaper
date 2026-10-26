"""Unit and integration tests: provenance graph, event log, firm rules, checks."""
import os
import tempfile

import pytest

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.gettempdir(), "wp_test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app import main as M  # noqa: E402
from app.checks import parse_text_as_read, run_checks  # noqa: E402
from app.events import EventStore, State, fingerprint  # noqa: E402
from app.packet import load_packet  # noqa: E402
from app.service import Service, tax_effect  # noqa: E402

P = load_packet()
SVC = Service(P)


@pytest.fixture(autouse=True)
def fresh_store():
    M.STORE = EventStore(os.environ["DATABASE_URL"])
    M.STORE.reset()
    yield


def client():
    return TestClient(M.app)


H = {"X-Actor": "st-01"}          # Priya, preparer
HR = {"X-Actor": "st-02"}         # Daniel, reviewer
HP = {"X-Actor": "st-03"}         # Helen, partner
HA = {"X-Actor": "st-05"}         # Jo, firm administrator
HC = {"X-Actor": "cu-01"}         # Ngozi, client
HM = {"X-Actor": "st-04"}         # Marcus, no clearance


# ----------------------------------------------------------------------------- packet / graph
def test_every_cited_source_resolves():
    bad = []
    for v in P.versions:
        for l in v["lines"]:
            for s in l.get("sources") or []:
                node = P.resolve_ref(s, v["version"])
                if node["kind"] == "unknown":
                    bad.append((v["version"], l["key"], s))
    assert not bad, bad[:10]


def test_every_input_exists_in_same_version():
    for v in P.versions:
        keys = {l["key"] for l in v["lines"]}
        for l in v["lines"]:
            for i in l.get("inputs") or []:
                assert i in keys, (v["version"], l["key"], i)


def test_downstream_reaches_agi_from_wages():
    assert "F1040.11" in P.downstream("F1040.1a")
    assert "F540NR.17" in P.downstream("F1040.1a") or "SchCA540NR.1.A" in P.downstream("F1040.1a")


def test_document_landing_explains_every_document():
    for d in P.documents:
        w = P.where_document_landed(d["id"])
        assert w["values_landed"] > 0 or w["why_not"], d["id"]


def test_json_pointer_refs():
    assert P.resolve_ref("py:/carryovers_into_2025/capital_loss_short")["data"] == 3200
    assert P.resolve_ref("agency:/efile/0/status")["data"] == "rejected"


def test_parse_text_as_read():
    assert parse_text_as_read("1,500.00", "money") == 1500
    assert parse_text_as_read("(2,150.00)", "money") == -2150
    assert parse_text_as_read("18 450,00", "money") == 18450
    assert parse_text_as_read("", "money") is None


# ----------------------------------------------------------------------------- tax effect
def test_tax_effect_uses_engine_rates_and_partner_threshold():
    te = tax_effect(P, "SchA.11", 7500, 1500)
    assert te["category"] == "itemized"
    assert te["federal"] == round(-6000 * P.version()["tax_effect_rates"]["itemized"]["federal_per_dollar"])
    assert te["requires_partner"] is True
    small = tax_effect(P, "SchB.1.1", 1840, 1900)
    assert small["requires_partner"] is False


# ----------------------------------------------------------------------------- event log
def test_state_folds_and_undo():
    s = M.STORE
    e1 = s.append("adjustment.proposed", "st-01", "preparer", {"old_value": 1, "new_value": 2, "status": "applied", "reason": "x"}, target="SchB.1.1", area="investments_and_digital_assets")
    st = State(s.all())
    assert st.effective_value("SchB.1.1", 1)[0] == 2
    s.append("undo", "st-01", "preparer", {"undone_event_id": e1.id})
    st = State(s.all())
    assert st.effective_value("SchB.1.1", 1)[0] == 1
    assert e1.id in st.undone


def test_batch_undo():
    s = M.STORE
    for k in ["SchB.1.1", "SchB.1.2"]:
        s.append("verification.recorded", "st-01", "preparer", {"type": "recalculated"}, target=k, batch_id="b1")
    s.append("undo", "st-01", "preparer", {"batch_id": "b1"})
    assert State(s.all()).verifications == []


def test_fingerprint_changes_with_values():
    assert fingerprint([("a", 1)]) != fingerprint([("a", 2)])
    assert fingerprint([("a", 1), ("b", 2)]) == fingerprint([("b", 2), ("a", 1)])


# ----------------------------------------------------------------------------- API + firm rules
def test_adjustment_small_applies_and_big_waits_for_partner():
    c = client()
    r = c.post("/api/adjustments", headers=H, json={"line_key": "SchB.1.1", "new_value": 1900, "reason": "agreed to 1099-INT"})
    assert r.status_code == 200 and r.json()["event"]["payload"]["status"] == "applied"
    r = c.post("/api/adjustments", headers=H, json={"line_key": "SchC.1", "new_value": 150000, "reason": "books-to-tax", "evidence": ["D14"]})
    assert r.json()["event"]["payload"]["status"] == "proposed"
    adj_id = r.json()["event"]["id"]
    # preparer cannot approve
    assert c.post("/api/adjustments/approve", headers=H, json={"adjustment_id": adj_id}).status_code == 403
    # partner approves -> applied, line shows new value
    assert c.post("/api/adjustments/approve", headers=HP, json={"adjustment_id": adj_id}).status_code == 200
    assert c.get("/api/lines/SchC.1", headers=H).json()["value"] == 150000


def test_signoff_reopens_when_scope_changes():
    c = client()
    assert c.post("/api/signoffs", headers=HR, json={"scope": "investments_and_digital_assets", "level": "reviewer"}).status_code == 200
    r = c.post("/api/adjustments", headers=H, json={"line_key": "SchB.1.1", "new_value": 1900, "reason": "x"})
    assert len(r.json()["reopened"]) == 1
    so = [s for s in c.get("/api/overview", headers=H).json()["signoffs"]]
    assert so[0]["status"] == "reopened"


def test_cannot_review_own_work():
    c = client()
    c.post("/api/adjustments", headers=HR, json={"line_key": "SchB.1.1", "new_value": 1900, "reason": "x"})
    r = c.post("/api/signoffs", headers=HR, json={"scope": "investments_and_digital_assets", "level": "reviewer"})
    assert r.status_code == 403


def test_blocking_note_blocks_partner_and_filing():
    c = client()
    c.post("/api/notes", headers=HR, json={"target": "SchC.1", "text": "reconcile", "blocking": True})
    assert c.post("/api/signoffs", headers=HP, json={"scope": "return", "level": "partner"}).status_code == 409
    assert c.post("/api/filing", headers=HP, json={"status": "sent_to_client"}).status_code == 409


def test_preparer_cannot_block():
    c = client()
    assert c.post("/api/notes", headers=H, json={"target": "SchC.1", "text": "x", "blocking": True}).status_code == 403


def test_judgment_requires_authority():
    c = client()
    assert c.post("/api/notes", headers=H, json={"target": "SchC.1", "text": "x", "kind": "judgment"}).status_code == 400
    assert c.post("/api/notes", headers=H, json={"target": "SchC.1", "text": "x", "kind": "judgment", "authority": "Reg. 1.263(a)-3"}).status_code == 200


def test_client_question_answer_becomes_evidence():
    c = client()
    q = c.post("/api/questions", headers=H, json={"to": "client", "text": "Which exchange?", "target": "F8949.H.C6"}).json()
    assert c.post("/api/questions/answer", headers=H, json={"question_id": q["id"], "answer": "x"}).status_code == 403
    assert c.post("/api/questions/answer", headers=HC, json={"question_id": q["id"], "answer": "Kraken, 2021"}).status_code == 200
    lv = c.get("/api/lines/F8949.H.C6", headers=H).json()
    assert lv["questions"][0]["status"] == "answered"


def test_filing_flow_freeze_and_amend():
    c = client()
    assert c.post("/api/signoffs", headers=HR, json={"scope": "return", "level": "reviewer"}).status_code == 200
    assert c.post("/api/signoffs", headers=HP, json={"scope": "return", "level": "partner"}).status_code == 200
    assert c.post("/api/filing", headers=HP, json={"status": "sent_to_client"}).status_code == 200
    # efile before client approval is refused
    assert c.post("/api/filing", headers=HP, json={"status": "efiled"}).status_code == 409
    assert c.post("/api/client/approve", headers=HC, json={"approved": True, "pin": "41207"}).status_code == 200
    assert c.post("/api/filing", headers=HP, json={"status": "efiled"}).status_code == 200
    assert c.post("/api/filing", headers=HP, json={"status": "accepted"}).status_code == 200
    # frozen: adjustments refused
    assert c.post("/api/adjustments", headers=H, json={"line_key": "SchB.1.1", "new_value": 1900, "reason": "x"}).status_code == 409
    assert c.post("/api/filing", headers=HP, json={"status": "amending"}).status_code == 200
    r = c.post("/api/adjustments", headers=H, json={"line_key": "SchB.1.1", "new_value": 1900, "reason": "x"})
    assert r.status_code == 200 and r.json()["event"]["payload"]["layer"] == "amendment"


def test_change_after_client_signature_voids_approval():
    c = client()
    c.post("/api/signoffs", headers=HR, json={"scope": "return", "level": "reviewer"})
    c.post("/api/signoffs", headers=HP, json={"scope": "return", "level": "partner"})
    c.post("/api/filing", headers=HP, json={"status": "sent_to_client"})
    c.post("/api/client/approve", headers=HC, json={"approved": True, "pin": "41207"})
    c.post("/api/adjustments", headers=HP, json={"line_key": "SchB.1.1", "new_value": 1900, "reason": "late 1099"})
    assert c.get("/api/overview", headers=H).json()["filing"]["status"] == "partner_approved"
    assert c.post("/api/filing", headers=HP, json={"status": "efiled"}).status_code == 409


def test_masking_and_view_log():
    c = client()
    masked = c.get("/api/documents/D71", headers=HM).json()["document"]["pages"][0]["printed_content"]
    assert "666-74-3390" not in masked and "3390" in masked
    clear = c.get("/api/documents/D71", headers=HR).json()["document"]["pages"][0]["printed_content"]
    assert "666-74-3390" in clear
    log = c.get("/api/firm", headers=HA).json()["view_log"]
    assert any(v["actor"] == "st-02" and v["subject"] == "D71" for v in log)
    assert c.get("/api/firm", headers=H).json()["view_log"] is None


def test_standards_change_affects_variance_flags():
    c = client()
    before = sum(1 for x in c.get("/api/checks", headers=H).json() if x["id"].startswith("variance:"))
    assert c.post("/api/standards", headers=H, json={"path": "variance_review.and_over_amount", "value": 100000}).status_code == 403
    assert c.post("/api/standards", headers=HA, json={"path": "variance_review.and_over_amount", "value": 100000}).status_code == 200
    after = sum(1 for x in c.get("/api/checks", headers=H).json() if x["id"].startswith("variance:"))
    assert after < before


def test_checks_find_planted_identity_error():
    res = run_checks(P, State([]))
    ids = {r["id"] for r in res}
    assert "ssn_prior_year:theo" in ids
    assert "ssn_mismatch:ev-1080" in ids
    assert "partial_extraction:D31" in ids


def test_records_all_render():
    c = client()
    for r in c.get("/api/records", headers=H).json():
        assert c.get(f"/api/records/{r['id']}", headers=H).status_code == 200, r


def test_bulk_verify_single_undo():
    c = client()
    r = c.post("/api/verifications/bulk", headers=H, json={"targets": ["SchB.1.1", "SchB.1.2", "SchB.1.3"], "type": "agreed_to_source_document"})
    assert r.status_code == 200
    assert c.get("/api/lines/SchB.1.2", headers=H).json()["verified"]
    c.post("/api/undo", headers=H, json={"batch_id": r.json()["batch_id"]})
    assert not c.get("/api/lines/SchB.1.2", headers=H).json()["verified"]


# ----------------------------------------------------------------------------- server hygiene
def test_partner_threshold_reads_firm_rule_text():
    assert M.partner_threshold({"rules": ["Adjustments with tax effect over 2,500 need a partner."]}) == 2500
    assert M.partner_threshold({"rules": ["no number here"]}) == 1000
    assert M.partner_threshold({}) == 1000


def test_capabilities_are_served_with_each_actor():
    actors = {a["id"]: a for a in client().get("/api/meta").json()["actors"]}
    assert "approve_adjustment" in actors["st-03"]["capabilities"]      # partner
    assert "approve_adjustment" not in actors["st-01"]["capabilities"]  # preparer
    assert actors["cu-01"]["capabilities"] == ["answer_client_question", "attach", "client_approve"]
    assert actors["examiner"]["capabilities"] == []


@pytest.mark.skipif(not os.path.isdir(M.DIST), reason="UI not built")
def test_static_route_never_escapes_dist():
    c = client()
    # a client route and a traversal attempt both fall back to the SPA shell
    for path in ["/filing", "/../backend/app/main.py", "/%2e%2e/backend/app/main.py"]:
        r = c.get(path)
        assert r.status_code == 200 and b"<div id=\"root\"" in r.content, path
    assert c.get("/index.html").status_code == 200


def test_partner_queue_gates_whole_return_signoff():
    """The overview lists proposed adjustments; the whole-return partner sign-off is refused until they are decided."""
    c = client()
    c.post("/api/admin/seed", headers=HA)
    pending = c.get("/api/overview", headers=HP).json()["pending_adjustments"]
    assert pending and all(x["status"] == "proposed" for x in pending)
    r = c.post("/api/signoffs", json={"scope": "return", "level": "partner"}, headers=HP)
    assert r.status_code == 409 and "await partner approval" in r.json()["detail"]
    for x in pending:
        assert c.post("/api/adjustments/approve", json={"adjustment_id": x["id"], "approve": True}, headers=HP).status_code == 200
    assert c.get("/api/overview", headers=HP).json()["pending_adjustments"] == []
    assert c.post("/api/signoffs", json={"scope": "return", "level": "partner"}, headers=HP).status_code == 200
