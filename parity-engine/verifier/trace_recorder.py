"""Playwright golden-trace recorder for the legacy JSP application.

Drives the browser against http://localhost:8080 through the drawdown
workflow, captures API calls, form POSTs, DOM validation alerts and
navigations, and writes execution-trace.v1.json compliant files into
artifacts/golden-traces/.

Usage:
    python trace_recorder.py
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE_URL = "http://localhost:8080"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "golden-traces"

API_PREFIX = "/api/v1/"
PARITY_PREFIX = "/__parity/"
MAX_BODY_CHARS = 4000

# Phase C: minimal header allowlists for auth-bridge and anti-cache proofs.
# Stored lowercase to keep golden traces deterministic across Playwright versions.
REQUEST_HEADER_ALLOW = {"authorization", "x-actor-id", "x-actor-role", "cache-control", "pragma"}
RESPONSE_HEADER_ALLOW = {"cache-control", "pragma", "expires", "content-type"}


class RecorderContext:
    """Captures network, validation and navigation events for one scenario."""

    def __init__(self, page: Page, scenario_name: str, target_url: str = BASE_URL) -> None:
        self.page = page
        self.scenario_name = scenario_name
        self.target_url = target_url
        self.events: list[dict] = []
        self._pending: list[dict] = []
        self._closed = False
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        page.on("framenavigated", self._on_navigated)

    def close(self) -> None:
        """Detach hooks so later scenarios start with a clean slate."""
        self._closed = True
        for event, handler in (
            ("request", self._on_request),
            ("response", self._on_response),
            ("framenavigated", self._on_navigated),
        ):
            try:
                self.page.remove_listener(event, handler)
            except (AttributeError, KeyError, ValueError):
                pass

    @staticmethod
    def _recordable(url: str, method: str) -> bool:
        return API_PREFIX in url or PARITY_PREFIX in url or method == "POST"

    def _on_request(self, request) -> None:
        if self._closed or not self._recordable(request.url, request.method):
            return
        payload = None
        raw = request.post_data
        if raw:
            try:
                payload = json.loads(raw)
            except (ValueError, TypeError):
                payload = raw
        headers: dict[str, str] = {}
        try:
            for key, value in (request.headers or {}).items():
                if key.lower() in REQUEST_HEADER_ALLOW:
                    headers[key.lower()] = value
        except Exception:
            headers = {}
        event: dict = {
            "type": "network",
            "method": request.method,
            "url": request.url,
            "requestPayload": payload,
            "responseStatus": None,
            "responseBody": None,
        }
        if headers:
            event["requestHeaders"] = headers
        self._pending.append(event)
        self.events.append(event)

    def _on_response(self, response) -> None:
        if self._closed or not self._recordable(response.url, response.request.method):
            return
        body = None
        try:
            text = response.text()
        except Exception:
            text = ""
        if text:
            try:
                body = json.loads(text)
            except ValueError:
                body = text if len(text) <= MAX_BODY_CHARS else text[:MAX_BODY_CHARS]
        headers: dict[str, str] = {}
        try:
            for key, value in (response.headers or {}).items():
                if key.lower() in RESPONSE_HEADER_ALLOW:
                    headers[key.lower()] = value
        except Exception:
            headers = {}
        for event in reversed(self._pending):
            if (
                event["responseStatus"] is None
                and event["url"] == response.url
                and event["method"] == response.request.method
            ):
                event["responseStatus"] = response.status
                event["responseBody"] = body
                if headers:
                    event["responseHeaders"] = headers
                self._pending.remove(event)
                return

    def _on_navigated(self, frame) -> None:
        if self._closed or frame.url == "about:blank":
            return
        self.events.append({"type": "navigation", "url": frame.url})

    def goto(self, path: str) -> int | None:
        response = self.page.goto(self.target_url + path)
        self.page.wait_for_load_state()
        status = response.status if response else None
        if status is not None and status >= 400:
            self.events.append(
                {
                    "type": "validation",
                    "selector": "page",
                    "text": f"GET {path} returned HTTP {status}",
                }
            )
        return status

    def api(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict:
        """Blocking in-page fetch so page hooks capture the call.

        Runs inside the page context, so it shares the browser session
        cookies with the JSP workflow. Extra headers (Authorization,
        X-Actor-Id/Role) support Phase C auth-bridge and governance flows.
        """
        return self.page.evaluate(
            """async ({method, url, payload, headers}) => {
                 const init = {method, headers: Object.assign({'Content-Type': 'application/json'}, headers || {})};
                 if (payload !== undefined && payload !== null) init.body = JSON.stringify(payload);
                 const res = await fetch(url, init);
                 const text = await res.text();
                 let body = null;
                 try { body = text ? JSON.parse(text) : null; } catch (e) { body = text; }
                 return {status: res.status, body};
               }""",
            {"method": method, "url": path, "payload": payload, "headers": headers or {}},
        )

    def api_form(self, path: str, fields: dict[str, list[str]]) -> dict:
        """Blocking in-page form POST (urlencoded, like the JSP forms)."""
        return self.page.evaluate(
            """async ({url, fields}) => {
                 const params = new URLSearchParams();
                 for (const [k, vs] of Object.entries(fields)) for (const v of vs) params.append(k, v);
                 const res = await fetch(url, {method: 'POST', body: params});
                 return {status: res.status, url: res.url};
               }""",
            {"url": path, "fields": fields},
        )

    def reset(self) -> None:
        """Blocking reset for deterministic database/session state."""
        result = self.api("POST", "/__parity/reset")
        assert result["status"] == 200, f"reset failed: {result!r}"

    def capture_validation(self, selector: str = '[data-testid="validation-errors"]') -> str | None:
        locator = self.page.locator(selector)
        if locator.count():
            text = locator.first.inner_text().strip()
            if text:
                self.events.append({"type": "validation", "selector": selector, "text": text})
                return text
        return None

    def snapshot_state(self) -> dict:
        result = self.api("GET", "/__parity/state")
        assert result["status"] == 200, f"state snapshot failed: {result!r}"
        return result["body"]

    def trace(self, final_state: dict) -> dict:
        events = [e for e in self.events if e["type"] != "network" or e["responseStatus"] is not None]
        return {
            "scenarioName": self.scenario_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "targetUrl": self.target_url,
            "events": events,
            "finalStateSnapshot": final_state,
        }


class GoldenTraceRecorder:
    """Runs the golden scenarios against the legacy application."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def _context(self, name: str) -> RecorderContext:
        ctx = RecorderContext(self.page, name)
        ctx.goto("/dashboard")
        ctx.reset()
        return ctx

    def _finish(self, ctx: RecorderContext, filename: str) -> Path:
        try:
            state = ctx.snapshot_state()
            trace = ctx.trace(state)
        finally:
            ctx.close()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / filename
        path.write_text(json.dumps(trace, indent=2), encoding="utf-8")
        return path

    def _select_invoices(self, ctx: RecorderContext, *refs: str) -> None:
        ctx.goto("/invoices")
        rows = ctx.page.locator('[data-testid="invoice-row"]')
        if rows.count() == 0:
            # Fallback for a server still running without the Invoice
            # getters: submit the same form POST the page would submit.
            result = ctx.api_form("/invoices/select", {"invoiceRefs": list(refs)})
            assert result["status"] == 200, f"invoice select failed: {result!r}"
        else:
            for ref in refs:
                row = ctx.page.locator('[data-testid="invoice-row"]', has_text=ref)
                row.locator('[data-testid="invoice-checkbox"]').check()
            ctx.page.get_by_test_id("select-invoices").click()
            ctx.page.wait_for_url("**/drawdown")
            ctx.goto("/drawdown")
            return
        draft = ctx.api("GET", "/api/v1/draft")
        assert draft["status"] == 200 and draft["body"]["invoiceRefs"] == list(refs)
        ctx.goto("/drawdown")

    def _fill_drawdown(self, ctx: RecorderContext, amount: str, tenor: str, beneficiary: str) -> None:
        ctx.page.get_by_test_id("requested-amount").fill(amount)
        ctx.page.locator("#currency").select_option("USD")
        ctx.page.locator("#tenorDays").select_option(tenor)
        ctx.page.get_by_test_id("beneficiary-code").fill(beneficiary)
        ctx.page.get_by_test_id("continue").click()
        ctx.page.wait_for_url("**/attachments")

    def _add_attachment_ui(self, ctx: RecorderContext, filename: str) -> None:
        ctx.page.locator("#category").select_option("INVOICE_COPY")
        ctx.page.locator("#filename").fill(filename)
        ctx.page.locator("#fileType").fill("application/pdf")
        ctx.page.locator("#sizeBytes").fill("48210")
        ctx.page.locator("#add-attachment").click()
        ctx.page.wait_for_url("**/review")

    def _put_draft(
        self,
        ctx: RecorderContext,
        refs: list[str],
        amount: float,
        tenor: int,
        beneficiary: str,
        token: str,
    ) -> None:
        # The JSP form posts do not persist field state server-side, so the
        # draft is completed through the shared JSON facade on the same session.
        draft = {
            "invoiceRefs": refs,
            "requestedAmount": amount,
            "currency": "USD",
            "tenorDays": tenor,
            "beneficiaryCode": beneficiary,
            "termsAcknowledged": True,
            "submissionToken": token,
            "attachments": [],
        }
        result = ctx.api("PUT", "/api/v1/draft", draft)
        assert result["status"] == 200, f"draft update failed: {result!r}"

    def _attach_pdf(self, ctx: RecorderContext, filename: str) -> None:
        attachment = {
            "category": "INVOICE_COPY",
            "filename": filename,
            "fileType": "application/pdf",
            "sizeBytes": 48210,
        }
        result = ctx.api("POST", "/api/v1/draft/attachments", attachment)
        assert result["status"] == 200, f"attachment failed: {result!r}"

    def _submit_review(self, ctx: RecorderContext) -> None:
        ctx.goto("/review")
        ctx.page.locator("#termsAcknowledged").check()
        ctx.page.get_by_test_id("submit-request").click()
        ctx.page.wait_for_load_state()

    @staticmethod
    def _confirmation_ref(page: Page) -> str:
        text = page.get_by_test_id("confirmation").inner_text()
        match = re.search(r"Request\s+(\S+)\s+submitted", text)
        assert match, f"no confirmation reference in: {text!r}"
        return match.group(1)

    def scenario_valid_drawdown(self) -> Path:
        """Select USD invoices 101/102, request $1,000 for 30 days, submit."""
        ctx = self._context("scenario_valid_drawdown")
        self._select_invoices(ctx, "INV-2026-101", "INV-2026-102")
        self._fill_drawdown(ctx, "1000", "30", "BEN-US-123")
        self._add_attachment_ui(ctx, "invoice-copy.pdf")
        token = f"golden-valid-{uuid.uuid4().hex[:8]}"
        self._put_draft(ctx, ["INV-2026-101", "INV-2026-102"], 1000, 30, "BEN-US-123", token)
        self._attach_pdf(ctx, "invoice-copy.pdf")
        self._submit_review(ctx)
        ref = self._confirmation_ref(ctx.page)
        assert ref.startswith("REQ-2026-"), f"unexpected reference: {ref}"
        return self._finish(ctx, "scenario_1.json")

    @staticmethod
    def _eligibility(invoice: dict) -> str:
        # Mirrors Invoice.eligibility() in the legacy app.
        if invoice["status"] != "APPROVED":
            return "NOT_APPROVED"
        if float(invoice["financedAmount"]) > 0:
            return "ALREADY_FINANCED"
        if invoice["currency"] not in ("USD", "EUR"):
            return "UNSUPPORTED_CURRENCY"
        return "ELIGIBLE"

    def scenario_ineligible_invoice(self) -> Path:
        """Verify financed/pending invoices are rejected."""
        ctx = self._context("scenario_ineligible_invoice")
        ctx.goto("/invoices")
        if ctx.page.locator('[data-testid="invoice-row"]').count() > 0:
            for ref, badge in (("INV-2026-104", "ALREADY_FINANCED"), ("INV-2026-105", "NOT_APPROVED")):
                row = ctx.page.locator('[data-testid="invoice-row"]', has_text=ref)
                assert row.locator('[data-testid="invoice-checkbox"]').is_disabled(), f"{ref} should be disabled"
                assert badge in row.inner_text(), f"{ref} should show {badge}"
        listed = ctx.api("GET", "/api/v1/invoices")
        assert listed["status"] == 200
        by_ref = {i["ref"]: i for i in listed["body"]}
        for ref, badge in (("INV-2026-104", "ALREADY_FINANCED"), ("INV-2026-105", "NOT_APPROVED")):
            actual = self._eligibility(by_ref[ref])
            assert actual == badge, f"{ref} eligibility {actual} != {badge}"
            ctx.events.append(
                {
                    "type": "validation",
                    "selector": "/api/v1/invoices",
                    "text": f"{ref} is ineligible: {badge}",
                }
            )
        # Attempt to select the financed invoice and submit: the server
        # must refuse with an eligibility error on the Review page.
        result = ctx.api_form("/invoices/select", {"invoiceRefs": ["INV-2026-104"]})
        assert result["status"] == 200, f"invoice select failed: {result!r}"
        ctx.goto("/drawdown")
        self._fill_drawdown(ctx, "1000", "30", "BEN-US-123")
        self._add_attachment_ui(ctx, "invoice-copy.pdf")
        token = f"golden-ineligible-{uuid.uuid4().hex[:8]}"
        self._put_draft(ctx, ["INV-2026-104"], 1000, 30, "BEN-US-123", token)
        self._attach_pdf(ctx, "invoice-copy.pdf")
        self._submit_review(ctx)
        ctx.page.get_by_test_id("validation-errors").wait_for()
        text = ctx.capture_validation()
        assert text and "not eligible" in text, f"expected eligibility error, got: {text!r}"
        return self._finish(ctx, "scenario_2.json")

    def scenario_advance_rate_exceeded(self) -> Path:
        """Request $105,000 against invoice 101 (85% cap is $102,000)."""
        ctx = self._context("scenario_advance_rate_exceeded")
        self._select_invoices(ctx, "INV-2026-101")
        self._fill_drawdown(ctx, "105000", "30", "BEN-US-123")
        self._add_attachment_ui(ctx, "invoice-copy.pdf")
        token = f"golden-advance-{uuid.uuid4().hex[:8]}"
        self._put_draft(ctx, ["INV-2026-101"], 105000, 30, "BEN-US-123", token)
        self._attach_pdf(ctx, "invoice-copy.pdf")
        self._submit_review(ctx)
        ctx.page.get_by_test_id("validation-errors").wait_for()
        text = ctx.capture_validation()
        assert text and "102000" in text, f"expected advance-cap error, got: {text!r}"
        return self._finish(ctx, "scenario_3.json")

    def scenario_duplicate_submission(self) -> Path:
        """Submit twice with one token and capture the idempotency block."""
        ctx = self._context("scenario_duplicate_submission")
        self._select_invoices(ctx, "INV-2026-101", "INV-2026-102")
        self._fill_drawdown(ctx, "1000", "30", "BEN-US-123")
        self._add_attachment_ui(ctx, "invoice-copy.pdf")
        token = f"golden-duplicate-{uuid.uuid4().hex[:8]}"
        self._put_draft(ctx, ["INV-2026-101", "INV-2026-102"], 1000, 30, "BEN-US-123", token)
        self._attach_pdf(ctx, "invoice-copy.pdf")
        self._submit_review(ctx)
        first_ref = self._confirmation_ref(ctx.page)
        # Resubmit the exact same form: the invoices are now financed, so
        # the Review page must refuse with an eligibility error.
        ctx.page.go_back()
        ctx.page.wait_for_load_state()
        if ctx.page.locator("#termsAcknowledged").count() == 0:
            ctx.goto("/review")
        ctx.page.locator("#termsAcknowledged").check()
        ctx.page.get_by_test_id("submit-request").click()
        ctx.page.wait_for_load_state()
        ctx.page.get_by_test_id("validation-errors").wait_for()
        text = ctx.capture_validation()
        assert text and "not eligible" in text, f"expected duplicate block, got: {text!r}"
        # Reuse the same token with a still-eligible invoice: the token
        # idempotency path must return the existing reference without
        # creating a new request or financing anything twice.
        ctx.api("PUT", "/api/v1/draft", {
            "invoiceRefs": ["INV-2026-103"],
            "requestedAmount": 1000,
            "currency": "EUR",
            "tenorDays": 30,
            "beneficiaryCode": "BEN-US-123",
            "termsAcknowledged": True,
            "submissionToken": token,
            "attachments": [],
        })
        self._attach_pdf(ctx, "invoice-copy.pdf")
        self._submit_review(ctx)
        second_ref = self._confirmation_ref(ctx.page)
        assert second_ref == first_ref, f"idempotency broken: {first_ref} != {second_ref}"
        ctx.events.append(
            {
                "type": "validation",
                "selector": '[data-testid="confirmation"]',
                "text": f"Duplicate submission returned existing reference {second_ref}",
            }
        )
        path = self._finish(ctx, "scenario_4.json")
        state = json.loads(path.read_text(encoding="utf-8"))["finalStateSnapshot"]
        assert len(state["requests"]) == 2, "duplicate created a second request"
        inv103 = next(i for i in state["invoices"] if i["ref"] == "INV-2026-103")
        assert float(inv103["financedAmount"]) == 0, "duplicate financed invoice 103"
        return path

    def scenario_auth_bridge(self) -> Path:
        """MFE Auth Bridge & Anti-Cache Traversal (Scenario 5).

        Binds JSESSIONID to a signed Bearer token, mutates the draft with
        Authorization: Bearer, and keeps the session alive via heartbeat.
        """
        ctx = self._context("scenario_auth_bridge")
        bridge = ctx.api("GET", "/api/v1/auth/bridge")
        assert bridge["status"] == 200, f"bridge failed: {bridge!r}"
        body = bridge["body"] or {}
        assert body.get("token"), f"bridge missing token: {body!r}"
        assert body.get("sessionId"), f"bridge missing sessionId: {body!r}"
        assert body.get("actorId") == "maker-1", f"unexpected bridge actor: {body!r}"
        assert body.get("role") == "MAKER_1", f"unexpected bridge role: {body!r}"
        token = str(body["token"])
        assert len(token.split(".")) == 2, f"bridge token must be body.signature: {token[:24]}..."
        draft = {
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
        assert put["status"] == 200, f"Bearer draft update failed: {put!r}"
        via_session = ctx.api("GET", "/api/v1/draft")
        assert via_session["status"] == 200
        assert (via_session["body"] or {}).get("submissionToken") == "golden-auth-bridge-01"
        heartbeat = ctx.api("POST", "/api/v1/auth/heartbeat", {}, {"Authorization": f"Bearer {token}"})
        assert heartbeat["status"] == 200, f"heartbeat failed: {heartbeat!r}"
        hb_body = heartbeat["body"] or {}
        assert hb_body.get("valid") is True, f"heartbeat not valid: {hb_body!r}"
        assert hb_body.get("sessionId") == body["sessionId"], "heartbeat session drifted"
        assert hb_body.get("remainingTtlSeconds", 0) > 0, f"heartbeat TTL missing: {hb_body!r}"
        ctx.events.append(
            {
                "type": "validation",
                "selector": "/api/v1/auth/bridge",
                "text": f"Bridge bound session {body['sessionId']} to Bearer for maker-1",
            }
        )
        ctx.events.append(
            {
                "type": "validation",
                "selector": "/api/v1/auth/heartbeat",
                "text": "Heartbeat valid, parent JSP session and MFE state synchronized",
            }
        )
        return self._finish(ctx, "scenario_5.json")

    def scenario_governance(self) -> Path:
        """4-Eyes Maker / Checker1 / Checker2 governance (Scenario 6)."""
        ctx = self._context("scenario_governance")
        maker = {"X-Actor-Id": "maker-1", "X-Actor-Role": "MAKER_1"}
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
        created = ctx.api("POST", "/api/v1/requests/submit", draft, maker)
        assert created["status"] == 201, f"governance submit failed: {created!r}"
        ref = (created["body"] or {}).get("ref")
        assert ref, f"submit missing ref: {created!r}"
        assert (created["body"] or {}).get("approvalStage") == "PENDING_CHECKER_1"
        amended = ctx.api(
            "PUT", f"/api/v1/requests/{ref}/amend",
            {"requestedAmount": 6000, "tenorDays": 60}, maker,
        )
        assert amended["status"] == 200, f"amend failed: {amended!r}"
        assert (amended["body"] or {}).get("approvalStage") == "PENDING_CHECKER_1"
        sod1 = ctx.api(
            "POST", f"/api/v1/requests/{ref}/checker1", {"action": "APPROVE"},
            {"X-Actor-Id": "maker-1", "X-Actor-Role": "CHECKER_1"},
        )
        assert sod1["status"] == 400, f"maker-as-checker1 must be blocked: {sod1!r}"
        assert "Maker cannot act as First Checker" in str((sod1["body"] or {}).get("error", sod1["body"]))
        c1 = ctx.api(
            "POST", f"/api/v1/requests/{ref}/checker1", {"action": "APPROVE"},
            {"X-Actor-Id": "checker-1", "X-Actor-Role": "CHECKER_1"},
        )
        assert c1["status"] == 200, f"checker1 approve failed: {c1!r}"
        assert (c1["body"] or {}).get("approvalStage") == "PENDING_CHECKER_2"
        sod2 = ctx.api(
            "POST", f"/api/v1/requests/{ref}/checker2", {"action": "APPROVE"},
            {"X-Actor-Id": "checker-1", "X-Actor-Role": "CHECKER_2"},
        )
        assert sod2["status"] == 400, f"checker1-as-checker2 must be blocked: {sod2!r}"
        c2 = ctx.api(
            "POST", f"/api/v1/requests/{ref}/checker2", {"action": "APPROVE"},
            {"X-Actor-Id": "checker-2", "X-Actor-Role": "CHECKER_2"},
        )
        assert c2["status"] == 200, f"checker2 approve failed: {c2!r}"
        assert (c2["body"] or {}).get("approvalStage") == "APPROVED"
        ctx.events.append(
            {
                "type": "validation",
                "selector": "/api/v1/requests",
                "text": f"Request {ref} approved by checker-1 then checker-2",
            }
        )
        path = self._finish(ctx, "scenario_6.json")
        state = json.loads(path.read_text(encoding="utf-8"))["finalStateSnapshot"]
        row = next((r for r in state["requests"] if r["ref"] == ref), None)
        assert row is not None and row["approvalStage"] == "APPROVED", "governance final stage drifted"
        return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            recorder = GoldenTraceRecorder(page)
            for name in (
                "scenario_valid_drawdown",
                "scenario_ineligible_invoice",
                "scenario_advance_rate_exceeded",
                "scenario_duplicate_submission",
                "scenario_auth_bridge",
                "scenario_governance",
            ):
                path = getattr(recorder, name)()
                print(f"{name} -> {path}")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
