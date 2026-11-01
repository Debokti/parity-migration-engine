"""Replay a golden trace against the modern Angular frontend.

Reads recorded inputs from a legacy golden trace, drives the Angular app at
http://localhost:4200 through the same workflow, and writes an
execution-trace.v1.json compliant replay file into artifacts/replays/.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verifier.trace_recorder import RecorderContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MODERN_URL = "http://localhost:4200"
LEGACY_URL = "http://localhost:8080"
REPLAY_DIR = ROOT / "artifacts" / "replays"


def _network_events(trace: dict) -> list[dict]:
    return [e for e in trace.get("events", []) if e.get("type") == "network"]


def _last(events: list[dict], method: str, suffix: str) -> dict | None:
    for event in reversed(events):
        url = str(event.get("url", "")).split("?")[0]
        if event.get("method") == method and urlsplit(url).path.endswith(suffix):
            return event
    return None


def _payload_values(payload: object) -> dict[str, list]:
    if isinstance(payload, dict):
        return {k: (v if isinstance(v, list) else [v]) for k, v in payload.items()}
    if isinstance(payload, str):
        out: dict[str, list] = {}
        for key, value in parse_qsl(payload, keep_blank_values=True):
            out.setdefault(key, []).append(value)
        return out
    return {}


def extract_inputs(trace: dict) -> dict:
    """Read replay inputs (refs, draft fields, attachment, token) from a golden trace."""
    events = _network_events(trace)
    refs: list[str] = []
    selected = _last(events, "POST", "/invoices/select")
    if selected is not None:
        refs = [str(v) for v in _payload_values(selected.get("requestPayload")).get("invoiceRefs", [])]
    puts = [e.get("requestPayload") for e in events
            if e.get("method") == "PUT" and urlsplit(str(e.get("url", "")).split("?")[0]).path.endswith("/api/v1/draft")]
    puts = [p for p in puts if isinstance(p, dict)]
    draft = puts[-1] if puts else {}
    refs = refs or [str(v) for v in draft.get("invoiceRefs", [])]
    attach_event = _last(events, "POST", "/api/v1/draft/attachments")
    attachment = attach_event.get("requestPayload") if attach_event else None
    attachment = attachment if isinstance(attachment, dict) else {}
    token = draft.get("submissionToken") or f"replay-{uuid.uuid4().hex[:8]}"
    return {
        "refs": refs,
        "amount": draft.get("requestedAmount"),
        "currency": draft.get("currency"),
        "tenor": draft.get("tenorDays"),
        "beneficiary": draft.get("beneficiaryCode"),
        "attachment": attachment,
        "token": token,
        "puts": puts,
    }


def extract_governance_inputs(trace: dict) -> dict:
    """Read governance replay inputs (submit draft, amend patch) from a golden trace."""
    events = _network_events(trace)
    submit = _last(events, "POST", "/api/v1/requests/submit")
    draft = submit.get("requestPayload") if submit else None
    draft = draft if isinstance(draft, dict) else {}
    amend_payload: dict = {}
    for event in events:
        url = str(event.get("url", "")).split("?")[0]
        path = urlsplit(url).path
        if event.get("method") == "PUT" and "/api/v1/requests/" in path and path.endswith("/amend"):
            payload = event.get("requestPayload")
            if isinstance(payload, dict):
                amend_payload = payload
    if not amend_payload:
        amend_payload = {"requestedAmount": 6000, "tenorDays": 60}
    return {"draft": draft, "amend": amend_payload}


def _bridge_token_from_events(events: list[dict]) -> str | None:
    for event in reversed(events):
        url = str(event.get("url", "")).split("?")[0]
        if urlsplit(url).path.endswith("/api/v1/auth/bridge"):
            body = event.get("responseBody")
            if isinstance(body, dict) and body.get("token"):
                return str(body["token"])
    return None


def _fill_invoices(page, refs: list[str]) -> None:
    for ref in refs:
        page.get_by_test_id(f"invoice-{ref}").check()
    page.get_by_test_id("submit-invoices").click()


def _fill_drawdown(page, amount, currency, tenor, beneficiary) -> None:
    if amount is not None:
        page.get_by_test_id("amount").fill(str(amount))
    if currency:
        page.get_by_test_id("currency").select_option(str(currency))
    if tenor is not None:
        page.get_by_test_id("tenorDays").select_option(str(tenor))
    if beneficiary:
        page.get_by_test_id("beneficiaryCode").fill(str(beneficiary))
    page.get_by_test_id("submit-drawdown").click()


def _add_attachment(page, attachment: dict) -> None:
    page.get_by_test_id("category").select_option(str(attachment.get("category", "INVOICE_COPY")))
    page.get_by_test_id("filename").fill(str(attachment.get("filename", "invoice-copy.pdf")))
    page.get_by_test_id("fileType").fill(str(attachment.get("fileType", "application/pdf")))
    page.get_by_test_id("sizeBytes").fill(str(attachment.get("sizeBytes", 48210)))
    with page.expect_response("**/attachments", timeout=15000):
        page.get_by_test_id("submit-attachment").click()


def _sync(page) -> None:
    with page.expect_response("**/api/v1/draft", timeout=15000):
        page.get_by_test_id("sync-draft").click()


def _submit_review(page) -> None:
    page.get_by_test_id("ackTerms").check()
    with page.expect_response("**/review/submit", timeout=15000):
        page.get_by_test_id("submit-review").click()


def _run_standard_flow(page, ctx: RecorderContext, inputs: dict) -> None:
    _fill_invoices(page, inputs["refs"])
    _fill_drawdown(page, inputs["amount"], inputs["currency"], inputs["tenor"], inputs["beneficiary"])
    _sync(page)
    _add_attachment(page, inputs["attachment"])
    _submit_review(page)


def _run_duplicate_flow(page, ctx: RecorderContext, inputs: dict) -> None:
    puts = inputs["puts"]
    first = puts[0] if puts else {}
    refs = [str(v) for v in first.get("invoiceRefs", inputs["refs"])]
    _fill_invoices(page, refs)
    _fill_drawdown(page, first.get("requestedAmount"), first.get("currency"),
                   first.get("tenorDays"), first.get("beneficiaryCode"))
    _sync(page)
    _add_attachment(page, inputs["attachment"])
    _submit_review(page)
    with page.expect_response("**/review/submit", timeout=15000):
        page.get_by_test_id("submit-review").click()
    page.wait_for_load_state()
    ctx.capture_validation()
    if len(puts) > 1:
        second = dict(puts[1])
        second["submissionToken"] = inputs["token"]
        put = ctx.api("PUT", "/api/v1/draft", second)
        assert put["status"] == 200, f"phase-3 draft update failed: {put!r}"
        attached = ctx.api("POST", "/api/v1/draft/attachments", inputs["attachment"] or {
            "category": "INVOICE_COPY", "filename": "invoice-copy.pdf",
            "fileType": "application/pdf", "sizeBytes": 48210})
        assert attached["status"] == 200, f"phase-3 attachment failed: {attached!r}"
        _submit_review(page)


def _run_auth_bridge_flow(page, ctx: RecorderContext, inputs: dict) -> None:
    """Replay Scenario 5 through the Angular MFE auth bridge."""
    try:
        page.get_by_test_id("auth-bridge-status").wait_for(timeout=15000)
    except Exception:
        pass
    token = _bridge_token_from_events(ctx.events)
    if not token:
        bridge = ctx.api("GET", "/api/v1/auth/bridge")
        assert bridge["status"] == 200, f"replay bridge failed: {bridge!r}"
        token = str((bridge["body"] or {}).get("token") or "")
        assert token, f"replay bridge missing token: {bridge!r}"
    puts = inputs.get("puts") or []
    draft = dict(puts[0]) if puts else {
        "invoiceRefs": ["INV-2026-101"],
        "requestedAmount": 5000,
        "currency": "USD",
        "tenorDays": 30,
        "beneficiaryCode": "BEN-US-001",
        "termsAcknowledged": True,
        "submissionToken": "golden-auth-bridge-01",
        "attachments": [],
    }
    put = ctx.api("PUT", "/api/v1/draft", draft, {"Authorization": f"Bearer {token}"})
    assert put["status"] == 200, f"replay Bearer draft failed: {put!r}"
    heartbeat = ctx.api("POST", "/api/v1/auth/heartbeat", {}, {"Authorization": f"Bearer {token}"})
    assert heartbeat["status"] == 200, f"replay heartbeat failed: {heartbeat!r}"
    assert (heartbeat["body"] or {}).get("valid") is True, f"replay heartbeat invalid: {heartbeat!r}"


def _run_governance_flow(page, ctx: RecorderContext, inputs: dict) -> None:
    """Replay Scenario 6 governance steps through the Angular proxy facade."""
    draft = dict(inputs.get("draft") or {})
    if not draft:
        draft = {
            "invoiceRefs": ["INV-2026-101", "INV-2026-102"],
            "requestedAmount": 5000,
            "currency": "USD",
            "tenorDays": 30,
            "beneficiaryCode": "BEN-US-001",
            "termsAcknowledged": True,
            "submissionToken": "golden-governance-01",
            "attachments": [
                {
                    "category": "INVOICE_COPY",
                    "filename": "invoice-copy.pdf",
                    "fileType": "application/pdf",
                    "sizeBytes": 48210,
                }
            ],
        }
    amend_patch = dict(inputs.get("amend") or {"requestedAmount": 6000, "tenorDays": 60})
    maker = {"X-Actor-Id": "maker-1", "X-Actor-Role": "MAKER_1"}
    created = ctx.api("POST", "/api/v1/requests/submit", draft, maker)
    assert created["status"] == 201, f"replay governance submit failed: {created!r}"
    ref = str((created["body"] or {}).get("ref") or "")
    assert ref, f"replay submit missing ref: {created!r}"
    amended = ctx.api("PUT", f"/api/v1/requests/{ref}/amend", amend_patch, maker)
    assert amended["status"] == 200, f"replay amend failed: {amended!r}"
    sod1 = ctx.api(
        "POST", f"/api/v1/requests/{ref}/checker1", {"action": "APPROVE"},
        {"X-Actor-Id": "maker-1", "X-Actor-Role": "CHECKER_1"},
    )
    assert sod1["status"] == 400, f"replay SoD-1 must be blocked: {sod1!r}"
    c1 = ctx.api(
        "POST", f"/api/v1/requests/{ref}/checker1", {"action": "APPROVE"},
        {"X-Actor-Id": "checker-1", "X-Actor-Role": "CHECKER_1"},
    )
    assert c1["status"] == 200, f"replay checker1 failed: {c1!r}"
    sod2 = ctx.api(
        "POST", f"/api/v1/requests/{ref}/checker2", {"action": "APPROVE"},
        {"X-Actor-Id": "checker-1", "X-Actor-Role": "CHECKER_2"},
    )
    assert sod2["status"] == 400, f"replay SoD-2 must be blocked: {sod2!r}"
    c2 = ctx.api(
        "POST", f"/api/v1/requests/{ref}/checker2", {"action": "APPROVE"},
        {"X-Actor-Id": "checker-2", "X-Actor-Role": "CHECKER_2"},
    )
    assert c2["status"] == 200, f"replay checker2 failed: {c2!r}"


def replay_trace(
    golden_path: str | Path,
    output_path: str | Path | None = None,
    modern_url: str = MODERN_URL,
    legacy_url: str = LEGACY_URL,
) -> Path:
    golden_file = Path(golden_path)
    golden = json.loads(golden_file.read_text(encoding="utf-8"))
    scenario = golden.get("scenarioName")
    inputs = extract_inputs(golden)
    gov_inputs = extract_governance_inputs(golden) if scenario == "scenario_governance" else {}
    stem = golden_file.stem
    out = Path(output_path) if output_path else REPLAY_DIR / f"replay_{stem}.json"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            context.add_init_script(
                f"try {{ sessionStorage.setItem('submissionToken', {json.dumps(inputs['token'])}); }} catch (e) {{}}"
            )
            page = context.new_page()
            ctx = RecorderContext(page, f"replay_{stem}", target_url=modern_url)
            try:
                reset = page.request.post(f"{legacy_url}/__parity/reset")
                assert reset.ok, f"backend reset failed: {reset.status}"
                page.goto(modern_url)
                page.wait_for_load_state()
                if scenario == "scenario_duplicate_submission":
                    _run_duplicate_flow(page, ctx, inputs)
                elif scenario == "scenario_auth_bridge":
                    _run_auth_bridge_flow(page, ctx, inputs)
                elif scenario == "scenario_governance":
                    _run_governance_flow(page, ctx, gov_inputs)
                else:
                    _run_standard_flow(page, ctx, inputs)
                page.wait_for_load_state()
                ctx.capture_validation()
                state = page.request.get(f"{legacy_url}/__parity/state").json()
                trace = ctx.trace(state)
            finally:
                ctx.close()
        finally:
            browser.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(trace, indent=2), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        print("usage: trace_replayer.py <golden-trace.json> [output.json]")
        return 1
    path = replay_trace(args[0], args[1] if len(args) > 1 else None)
    print(f"replay written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
