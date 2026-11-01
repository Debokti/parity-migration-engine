"""Phase C offline checks: auth-bridge, governance, anti-cache, and ask context.

Runs without servers, browsers, or LLM calls.
"""
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parity_cli import (
    digest_golden_trace,
    load_ask_context,
    load_coexistence_evidence,
    report_totals_line,
)
from verifier.parity_differ import (
    _anti_cache_ok,
    _decode_bridge_payload,
    _diff_anti_cache,
    _diff_auth_bridge,
    _diff_bearer_draft,
    _diff_governance_stages,
    _diff_heartbeat,
    _has_bearer,
    _normalize_auth_body,
    diff_traces,
)
from verifier.trace_replayer import _bridge_token_from_events, extract_governance_inputs

ROOT = Path(__file__).resolve().parents[2]
TRACE_SCHEMA = json.loads((ROOT / "contracts/schemas/execution-trace.v1.json").read_text(encoding="utf-8"))


def _token(session_id: str) -> str:
    payload = {"sessionId": session_id, "actorId": "maker-1", "role": "MAKER_1",
               "issuedAt": 1700000000, "expiresAt": 1700001800, "epoch": 0}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = base64.urlsafe_b64encode(b"sig").decode().rstrip("=")
    return f"{body}.{sig}"


def _bridge_event(session_id: str, actor: str = "maker-1", role: str = "MAKER_1") -> dict:
    token = _token(session_id)
    return {"type": "network", "method": "GET", "url": "http://localhost:8080/api/v1/auth/bridge",
            "requestPayload": None, "responseStatus": 200,
            "responseBody": {"token": token, "sessionId": session_id, "actorId": actor,
                             "role": role, "issuedAt": 1700000000, "expiresAt": 1700001800}}


def test_golden_traces_validate():
    from jsonschema import Draft202012Validator

    for stem in ("scenario_5", "scenario_6"):
        trace = json.loads((ROOT / "artifacts" / "golden-traces" / f"{stem}.json").read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(TRACE_SCHEMA).iter_errors(trace))
        assert errors == [], f"{stem}: {[e.message for e in errors]}"


def test_golden_self_diff_passes(tmp_path):
    for stem in ("scenario_5", "scenario_6"):
        golden = ROOT / "artifacts" / "golden-traces" / f"{stem}.json"
        report, passed, total = diff_traces(golden, golden, tmp_path / f"parity_{stem}.json")
        assert report["matchPercentage"] == 100, f"{stem}: {report['discrepancies']}"
        assert report["discrepancies"] == []


def test_bridge_binding_and_actor_compare():
    legacy = [_bridge_event("golden-s1")]
    modern = [_bridge_event("replay-s9")]
    passed, total, discs = _diff_auth_bridge(legacy, modern)
    assert discs == [], discs
    assert passed == total and total > 0
    bad_role = [_bridge_event("replay-s9", role="CHECKER_1")]
    _, _, discs = _diff_auth_bridge(legacy, bad_role)
    assert discs, "role drift must be flagged"
    tampered = [_bridge_event("other-session")]
    tampered[0]["responseBody"]["sessionId"] = "mismatched"
    _, _, discs = _diff_auth_bridge(tampered, tampered)
    assert any(d["path"] == "$.authBridgeBinding" for d in discs)


def test_decode_bridge_payload_roundtrip():
    payload = _decode_bridge_payload(_token("s1"))
    assert payload and payload["sessionId"] == "s1"
    assert _decode_bridge_payload("not-a-token") is None


def test_heartbeat_ttl_normalized():
    def hb(ttl):
        return {"type": "network", "method": "POST", "url": "http://h/api/v1/auth/heartbeat",
                "requestPayload": {}, "responseStatus": 200,
                "responseBody": {"valid": True, "sessionId": "s", "actorId": "maker-1",
                                 "role": "MAKER_1", "remainingTtlSeconds": ttl}}
    passed, total, discs = _diff_heartbeat([hb(1799)], [hb(42)])
    assert discs == [], discs
    assert _normalize_auth_body({"remainingTtlSeconds": 1799}) == {"remainingTtlSeconds": "<ttl>"}
    _, _, discs = _diff_heartbeat([hb(1799)], [hb(0)])
    assert discs, "expired heartbeat must be flagged"


def test_bearer_draft_requires_auth_header():
    put = {"type": "network", "method": "PUT", "url": "http://h/api/v1/draft",
           "requestPayload": {}, "responseStatus": 200,
           "requestHeaders": {"authorization": "Bearer abc.def"}}
    assert _has_bearer(put) is True
    _, _, discs = _diff_bearer_draft([put], [put])
    assert discs == []
    naked = dict(put)
    naked.pop("requestHeaders")
    _, _, discs = _diff_bearer_draft([put], [naked])
    assert any(d["path"] == "$.bearerDraftAuth" for d in discs)


def test_anti_cache_headers():
    good = {"type": "network", "method": "GET", "url": "http://h/api/v1/draft",
            "responseStatus": 200,
            "responseHeaders": {"cache-control": "no-store, no-cache, must-revalidate, max-age=0",
                                "pragma": "no-cache", "expires": "0"}}
    assert _anti_cache_ok(good) == (True, True)
    _, _, discs = _diff_anti_cache([good], [good])
    assert discs == []
    bad = {"type": "network", "method": "GET", "url": "http://h/api/v1/draft",
           "responseStatus": 200, "responseHeaders": {"cache-control": "public, max-age=60"}}
    assert _anti_cache_ok(bad) == (False, False)
    _, _, discs = _diff_anti_cache([good], [bad])
    assert len(discs) == 2


def test_governance_stage_sequence():
    def ev(url_suffix, status, body):
        return {"type": "network", "method": "POST" if "checker" in url_suffix or "submit" in url_suffix else "PUT",
                "url": f"http://h/api/v1/requests/REQ-1{url_suffix}",
                "requestPayload": {}, "responseStatus": status, "responseBody": body}
    legacy = [
        ev("/submit", 201, {"ref": "REQ-1", "approvalStage": "PENDING_CHECKER_1"}),
        {"type": "network", "method": "PUT", "url": "http://h/api/v1/requests/REQ-1/amend",
         "requestPayload": {}, "responseStatus": 200,
         "responseBody": {"ref": "REQ-1", "approvalStage": "PENDING_CHECKER_1"}},
        ev("/checker1", 400, {"error": "Maker cannot act as First Checker"}),
        ev("/checker1", 200, {"ref": "REQ-1", "approvalStage": "PENDING_CHECKER_2"}),
        ev("/checker2", 400, {"error": "Second Checker must be distinct from Maker and First Checker"}),
        ev("/checker2", 200, {"ref": "REQ-1", "approvalStage": "APPROVED"}),
    ]
    passed, total, discs = _diff_governance_stages(legacy, [dict(e) for e in legacy])
    assert discs == [], discs
    assert passed == total and total > 0
    drifted = [dict(e) for e in legacy]
    drifted[-1] = dict(drifted[-1], responseBody={"ref": "REQ-1", "approvalStage": "REJECTED"})
    _, _, discs = _diff_governance_stages(legacy, drifted)
    assert discs, "final APPROVED drift must be flagged"


def test_governance_input_extraction():
    trace = json.loads((ROOT / "artifacts" / "golden-traces" / "scenario_6.json").read_text(encoding="utf-8"))
    inputs = extract_governance_inputs(trace)
    assert inputs["draft"]["submissionToken"] == "golden-governance-01"
    assert inputs["amend"] == {"requestedAmount": 6000, "tenorDays": 60}
    trace5 = json.loads((ROOT / "artifacts" / "golden-traces" / "scenario_5.json").read_text(encoding="utf-8"))
    token = _bridge_token_from_events([e for e in trace5["events"] if e.get("type") == "network"])
    assert token and len(token.split(".")) == 2


def test_ask_context_loads_spec_and_reports():
    spec_text, summaries = load_ask_context()
    assert "scf-drawdown" in spec_text
    assert len(summaries) == 6
    assert summaries[0].startswith("scenario_1:")
    missing_spec, missing_reports = load_ask_context(
        spec_path=ROOT / "artifacts" / "specs" / "does-not-exist.json",
        reports_dir=ROOT / "artifacts" / "reports-missing",
    )
    assert "missing BehaviorSpec" in missing_spec
    assert all("report not found" in s for s in missing_reports)


def test_enriched_spec_covers_enterprise_phases():
    from jsonschema import Draft202012Validator

    schema = json.loads((ROOT / "contracts/schemas/behavior-spec.v1.json").read_text(encoding="utf-8"))
    spec = json.loads((ROOT / "artifacts" / "specs" / "drawdown-spec.json").read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(spec)) == []
    names = [s["name"] for s in spec["steps"]]
    assert "Bridge JSESSIONID to Bearer token" in names
    assert "Second checker approves (4-eyes)" in names
    assert "Hold parity and coverage gates" in names
    ids = {i["id"] for i in spec["domainInvariants"]}
    assert {"auth-bridge-binding", "anti-cache-headers", "mfe-coexistence",
            "governance-sod-1", "governance-sod-2", "parity-gates",
            "coverage-gates"} <= ids


def test_ask_summaries_include_offline_check_counts():
    _, summaries = load_ask_context()
    assert len(summaries) == 6
    for summary in summaries:
        assert "checks" in summary or "report not found" in summary or "unreadable" in summary
    if all((ROOT / "artifacts" / "replays" / f"replay_scenario_{i}.json").is_file() for i in range(1, 7)):
        totals = report_totals_line(summaries)
        assert totals == "total: 699/699 checks across 6 scenarios"
        assert "113/113 checks" in summaries[0]
        assert "179/179 checks" in summaries[5]


def test_report_totals_line_parses_counts():
    assert report_totals_line(["scenario_1: 100.0% match, 113/113 checks, 0 discrepancies",
                               "scenario_2: report not found"]) == "total: 113/113 checks across 1 scenarios"
    assert report_totals_line(["scenario_1: report not found"]) is None


def test_golden_digests_expose_bridge_and_governance_markers():
    digest5 = digest_golden_trace("scenario_5")
    for marker in ("/api/v1/auth/bridge", "Authorization: Bearer", "no-store",
                   "/api/v1/auth/heartbeat", "valid=True", "remainingTtlSeconds=>0"):
        assert marker in digest5, marker
    assert "eyJzZXNzaW9uSWQi" not in digest5
    digest6 = digest_golden_trace("scenario_6")
    for marker in ("PENDING_CHECKER_1", "checker1", "400", "Maker cannot act as First Checker",
                   "PENDING_CHECKER_2", "Second Checker must be distinct", "APPROVED"):
        assert marker in digest6, marker
    assert "golden trace not found" in digest_golden_trace("scenario_99")


def test_coexistence_evidence_reads_build_files():
    evidence = load_coexistence_evidence()
    assert "0.85" in evidence
    assert "ag-grid-community" in evidence
    assert "northstarDrawdown" in evidence
    assert "remoteEntry" in evidence
    assert "northstar-drawdown-mfe" in evidence
    assert "not found" in load_coexistence_evidence(root=ROOT / "does-not-exist")
