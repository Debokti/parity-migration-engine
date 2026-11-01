"""Deterministic parity diffing between golden traces and modern replays."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "artifacts" / "reports"
SCHEMA_FILE = ROOT / "contracts" / "schemas" / "parity-report.v1.json"

VOLATILE_KEYS = {"createdAt", "created_at", "timestamp"}
DOM_ALERT_SELECTOR = '[data-testid="validation-errors"]'

REQUIRED_CACHE_DIRECTIVES = {"no-store", "no-cache", "must-revalidate"}


def compare(expected: object, actual: object, path: str = "$") -> list[dict]:
    if expected == actual:
        return []
    return [{"path": path, "kind": "payload", "message": "values differ"}]


def _normalize(node: object) -> object:
    if isinstance(node, dict):
        return {k: _normalize(v) for k, v in node.items() if k not in VOLATILE_KEYS}
    if isinstance(node, list):
        return [_normalize(v) for v in node]
    return node


def _diff_values(expected: object, actual: object, path: str, mismatch_kind: str, missing_kind: str):
    """Deep-compare two JSON values. Returns (passed, total, discrepancies)."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        passed = total = 0
        discrepancies = []
        for key in sorted(set(expected) | set(actual)):
            sub = f"{path}.{key}"
            if key not in expected:
                total += 1
                discrepancies.append({"kind": missing_kind, "path": sub, "expected": None,
                                      "actual": actual[key], "detail": f"unexpected key {sub}"})
            elif key not in actual:
                total += 1
                discrepancies.append({"kind": missing_kind, "path": sub, "expected": expected[key],
                                      "actual": None, "detail": f"missing key {sub}"})
            else:
                sub_passed, sub_total, sub_disc = _diff_values(
                    expected[key], actual[key], sub, mismatch_kind, missing_kind)
                passed += sub_passed
                total += sub_total
                discrepancies.extend(sub_disc)
        return passed, total, discrepancies
    if isinstance(expected, list) and isinstance(actual, list):
        passed, total, discrepancies = 0, 1, []
        if len(expected) != len(actual):
            discrepancies.append({"kind": mismatch_kind, "path": f"{path}.length", "expected": expected,
                                  "actual": actual, "detail": f"array length differs at {path}"})
        else:
            passed += 1
        for index, (exp_item, act_item) in enumerate(zip(expected, actual)):
            sub_passed, sub_total, sub_disc = _diff_values(
                exp_item, act_item, f"{path}[{index}]", mismatch_kind, missing_kind)
            passed += sub_passed
            total += sub_total
            discrepancies.extend(sub_disc)
        return passed, total, discrepancies
    if expected == actual:
        return 1, 1, []
    return 0, 1, [{"kind": mismatch_kind, "path": path, "expected": expected,
                   "actual": actual, "detail": f"value differs at {path}"}]


def _network_events(trace: dict) -> list[dict]:
    return [e for e in trace.get("events", []) if e.get("type") == "network"]


def _matching(events: list[dict], method: str, suffix: str) -> list[dict]:
    return [e for e in events
            if e.get("method") == method and urlsplit(str(e.get("url", "")).split("?")[0]).path.endswith(suffix)]


def _clean(text: str) -> str:
    return " ".join(str(text).split())


def _is_bridge_token(value: object) -> bool:
    return isinstance(value, str) and len(value.split(".")) == 2 and len(value) > 16


def _decode_bridge_payload(token: str) -> dict | None:
    try:
        first = token.split(".")[0]
        padded = first + "=" * (-len(first) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _normalize_auth_body(body: object) -> object:
    if isinstance(body, dict):
        out: dict = {}
        for key, value in body.items():
            if key == "token":
                out[key] = "<bearer>" if _is_bridge_token(value) else value
            elif key in ("issuedAt", "expiresAt", "remainingTtlSeconds"):
                out[key] = "<ttl>" if isinstance(value, (int, float)) and value > 0 else value
            elif key == "sessionId":
                out[key] = "<session>" if value else value
            elif key in VOLATILE_KEYS:
                continue
            else:
                out[key] = _normalize_auth_body(value)
        return out
    if isinstance(body, list):
        return [_normalize_auth_body(v) for v in body]
    return body


def _normalize_gov_body(body: object) -> object:
    if isinstance(body, dict):
        out: dict = {}
        for key, value in body.items():
            if key == "ref":
                out[key] = "<ref>" if value else value
            elif key in VOLATILE_KEYS:
                continue
            else:
                out[key] = _normalize_gov_body(value)
        return out
    if isinstance(body, list):
        return [_normalize_gov_body(v) for v in body]
    return body


def _has_bearer(event: dict) -> bool:
    headers = event.get("requestHeaders") or {}
    auth = str(headers.get("authorization", ""))
    return auth.startswith("Bearer ") and len(auth) > 7


def _anti_cache_ok(event: dict) -> tuple[bool, bool]:
    headers = event.get("responseHeaders") or {}
    cache = str(headers.get("cache-control", "")).lower()
    pragma = str(headers.get("pragma", "")).lower().strip()
    directives = {part.strip() for part in cache.split(",") if part.strip()}
    return REQUIRED_CACHE_DIRECTIVES.issubset(directives), pragma == "no-cache"


def _api_events(events: list[dict]) -> list[dict]:
    return [e for e in events if "/api/v1/" in str(e.get("url", ""))]


def _diff_auth_bridge(legacy_net: list[dict], modern_net: list[dict]):
    legacy = _matching(legacy_net, "GET", "/api/v1/auth/bridge")
    modern = _matching(modern_net, "GET", "/api/v1/auth/bridge")
    if not legacy and not modern:
        return 0, 0, []
    if not legacy or not modern:
        side = "replay" if legacy else "golden"
        return 0, 1, [{"kind": "status-mismatch", "path": "$.authBridge",
                       "expected": bool(legacy), "actual": bool(modern),
                       "detail": f"GET /api/v1/auth/bridge missing on {side} side"}]
    passed, total, discs = _diff_values(
        [e.get("responseStatus") for e in legacy],
        [e.get("responseStatus") for e in modern],
        "$.authBridgeStatus", "status-mismatch", "status-mismatch")
    p2, t2, d2 = _diff_values(
        [_normalize_auth_body(e.get("responseBody")) for e in legacy],
        [_normalize_auth_body(e.get("responseBody")) for e in modern],
        "$.authBridgeBody", "payload-mismatch", "payload-mismatch")
    passed += p2
    total += t2
    discs.extend(d2)
    for label, event in (("golden", legacy[-1]), ("replay", modern[-1])):
        body = event.get("responseBody") if isinstance(event.get("responseBody"), dict) else {}
        token = str(body.get("token", ""))
        total += 1
        payload = _decode_bridge_payload(token) if _is_bridge_token(token) else None
        if payload and payload.get("sessionId") == body.get("sessionId"):
            passed += 1
        else:
            discs.append({"kind": "payload-mismatch", "path": "$.authBridgeBinding",
                          "expected": body.get("sessionId"), "actual": (payload or {}).get("sessionId"),
                          "detail": f"Bearer token must bind JSESSIONID on {label} side"})
    return passed, total, discs


def _diff_heartbeat(legacy_net: list[dict], modern_net: list[dict]):
    legacy = _matching(legacy_net, "POST", "/api/v1/auth/heartbeat")
    modern = _matching(modern_net, "POST", "/api/v1/auth/heartbeat")
    if not legacy and not modern:
        return 0, 0, []
    if not legacy or not modern:
        side = "replay" if legacy else "golden"
        return 0, 1, [{"kind": "status-mismatch", "path": "$.heartbeat",
                       "expected": bool(legacy), "actual": bool(modern),
                       "detail": f"POST /api/v1/auth/heartbeat missing on {side} side"}]
    passed, total, discs = _diff_values(
        [e.get("responseStatus") for e in legacy],
        [e.get("responseStatus") for e in modern],
        "$.heartbeatStatus", "status-mismatch", "status-mismatch")
    p2, t2, d2 = _diff_values(
        [_normalize_auth_body(e.get("responseBody")) for e in legacy],
        [_normalize_auth_body(e.get("responseBody")) for e in modern],
        "$.heartbeatBody", "payload-mismatch", "payload-mismatch")
    passed += p2
    total += t2
    discs.extend(d2)
    for label, events in (("golden", legacy), ("replay", modern)):
        total += 1
        bodies = [e.get("responseBody") for e in events if isinstance(e.get("responseBody"), dict)]
        if bodies and all(b.get("valid") is True and (b.get("remainingTtlSeconds", 0) or 0) > 0 for b in bodies):
            passed += 1
        else:
            discs.append({"kind": "payload-mismatch", "path": "$.heartbeatLiveness",
                          "expected": True, "actual": [b.get("valid") for b in bodies],
                          "detail": f"heartbeat must stay valid with TTL on {label} side"})
    return passed, total, discs


def _diff_bearer_draft(legacy_net: list[dict], modern_net: list[dict]):
    legacy = _matching(legacy_net, "PUT", "/api/v1/draft")
    modern = _matching(modern_net, "PUT", "/api/v1/draft")
    if not legacy and not modern:
        return 0, 0, []
    passed = total = 0
    discs: list[dict] = []
    for label, events in (("golden", legacy), ("replay", modern)):
        total += 1
        if events and all(_has_bearer(e) for e in events):
            passed += 1
        else:
            discs.append({"kind": "payload-mismatch", "path": "$.bearerDraftAuth",
                          "expected": "Bearer <token>", "actual": None,
                          "detail": f"PUT /api/v1/draft must carry Authorization Bearer on {label} side"})
    return passed, total, discs


def _diff_anti_cache(legacy_net: list[dict], modern_net: list[dict]):
    legacy = [e for e in _api_events(legacy_net) if e.get("responseHeaders")]
    modern = [e for e in _api_events(modern_net) if e.get("responseHeaders")]
    if not legacy and not modern:
        return 0, 0, []
    passed = total = 0
    discs: list[dict] = []
    for label, events in (("golden", legacy), ("replay", modern)):
        for event in events:
            cache_ok, pragma_ok = _anti_cache_ok(event)
            total += 2
            if cache_ok:
                passed += 1
            else:
                discs.append({"kind": "payload-mismatch", "path": "$.antiCacheHeaders",
                              "expected": "no-store, no-cache, must-revalidate",
                              "actual": (event.get("responseHeaders") or {}).get("cache-control"),
                              "detail": f"Cache-Control anti-cache directives missing on {label} {event.get('url')}"})
            if pragma_ok:
                passed += 1
            else:
                discs.append({"kind": "payload-mismatch", "path": "$.antiCacheHeaders",
                              "expected": "no-cache",
                              "actual": (event.get("responseHeaders") or {}).get("pragma"),
                              "detail": f"Pragma no-cache missing on {label} {event.get('url')}"})
    return passed, total, discs


def _diff_governance_stages(legacy_net: list[dict], modern_net: list[dict]):
    passed = total = 0
    discs: list[dict] = []

    def absorb(result):
        nonlocal passed, total
        p, t, d = result
        passed += p
        total += t
        discs.extend(d)

    legacy_sub = _matching(legacy_net, "POST", "/api/v1/requests/submit")
    modern_sub = _matching(modern_net, "POST", "/api/v1/requests/submit")
    if legacy_sub or modern_sub:
        absorb(_diff_values(
            [_normalize_gov_body(e.get("responseBody")) for e in legacy_sub],
            [_normalize_gov_body(e.get("responseBody")) for e in modern_sub],
            "$.governanceSubmit", "payload-mismatch", "payload-mismatch"))

    def amend_events(events: list[dict]) -> list[dict]:
        out = []
        for event in events:
            path = urlsplit(str(event.get("url", "")).split("?")[0]).path
            if event.get("method") == "PUT" and "/api/v1/requests/" in path and path.endswith("/amend"):
                out.append(event)
        return out

    legacy_amend, modern_amend = amend_events(legacy_net), amend_events(modern_net)
    if legacy_amend or modern_amend:
        if legacy_amend and modern_amend:
            absorb(_diff_values(
                [e.get("responseStatus") for e in legacy_amend],
                [e.get("responseStatus") for e in modern_amend],
                "$.governanceAmendStatus", "status-mismatch", "status-mismatch"))
            absorb(_diff_values(
                [_normalize_gov_body(e.get("responseBody")) for e in legacy_amend],
                [_normalize_gov_body(e.get("responseBody")) for e in modern_amend],
                "$.governanceAmend", "payload-mismatch", "payload-mismatch"))
        else:
            total += 1
            side = "replay" if legacy_amend else "golden"
            discs.append({"kind": "status-mismatch", "path": "$.governanceAmend",
                          "expected": bool(legacy_amend), "actual": bool(modern_amend),
                          "detail": f"PUT /api/v1/requests/{{ref}}/amend missing on {side} side"})

    for level in (1, 2):
        suffix = f"/checker{level}"
        legacy_seq = [e for e in legacy_net
                      if e.get("method") == "POST" and urlsplit(str(e.get("url", "")).split("?")[0]).path.endswith(suffix)]
        modern_seq = [e for e in modern_net
                      if e.get("method") == "POST" and urlsplit(str(e.get("url", "")).split("?")[0]).path.endswith(suffix)]
        if not legacy_seq and not modern_seq:
            continue
        absorb(_diff_values(
            [e.get("responseStatus") for e in legacy_seq],
            [e.get("responseStatus") for e in modern_seq],
            f"$.governanceChecker{level}Status", "status-mismatch", "status-mismatch"))
        absorb(_diff_values(
            [_normalize_gov_body(e.get("responseBody")) for e in legacy_seq],
            [_normalize_gov_body(e.get("responseBody")) for e in modern_seq],
            f"$.governanceChecker{level}", "payload-mismatch", "payload-mismatch"))
    return passed, total, discs


def diff_traces(
    legacy_path: str | Path,
    modern_path: str | Path,
    output_path: str | Path | None = None,
) -> tuple[dict, int, int]:
    """Compare golden vs replay across network, validation, and state. Returns (report, passed, total)."""
    legacy_file, modern_file = Path(legacy_path), Path(modern_path)
    legacy = json.loads(legacy_file.read_text(encoding="utf-8"))
    modern = json.loads(modern_file.read_text(encoding="utf-8"))
    legacy_net, modern_net = _network_events(legacy), _network_events(modern)
    passed = total = 0
    discrepancies: list[dict] = []

    def absorb(result):
        nonlocal passed, total
        sub_passed, sub_total, sub_disc = result
        passed += sub_passed
        total += sub_total
        discrepancies.extend(sub_disc)

    legacy_submits = _matching(legacy_net, "POST", "/api/v1/requests/submit")
    modern_submits = _matching(modern_net, "POST", "/api/v1/requests/submit")
    if legacy_submits or modern_submits:
        absorb(_diff_values(
            [e.get("requestPayload") for e in legacy_submits],
            [e.get("requestPayload") for e in modern_submits],
            "$.apiSubmitPayloads", "payload-mismatch", "payload-mismatch"))
        absorb(_diff_values(
            [e.get("responseStatus") for e in legacy_submits],
            [e.get("responseStatus") for e in modern_submits],
            "$.apiSubmitStatus", "status-mismatch", "status-mismatch"))

    legacy_puts = _matching(legacy_net, "PUT", "/api/v1/draft")
    modern_puts = _matching(modern_net, "PUT", "/api/v1/draft")
    if legacy_puts or modern_puts:
        if legacy_puts and modern_puts:
            absorb(_diff_values(
                legacy_puts[-1].get("requestPayload"), modern_puts[-1].get("requestPayload"),
                "$.draftPayload", "payload-mismatch", "payload-mismatch"))
        else:
            total += 1
            side = "replay" if legacy_puts else "golden"
            discrepancies.append({"kind": "payload-mismatch", "path": "$.draftPayload",
                                  "expected": bool(legacy_puts), "actual": bool(modern_puts),
                                  "detail": f"PUT /api/v1/draft missing on {side} side"})

    legacy_posts = _matching(legacy_net, "POST", "/review/submit")
    modern_posts = _matching(modern_net, "POST", "/review/submit")
    if legacy_posts or modern_posts:
        if legacy_posts and modern_posts:
            absorb(_diff_values(
                legacy_posts[-1].get("responseStatus"), modern_posts[-1].get("responseStatus"),
                "$.reviewSubmitStatus", "status-mismatch", "status-mismatch"))
        else:
            total += 1
            side = "replay" if legacy_posts else "golden"
            discrepancies.append({"kind": "status-mismatch", "path": "$.reviewSubmitStatus",
                                  "expected": bool(legacy_posts), "actual": bool(modern_posts),
                                  "detail": f"POST /review/submit missing on {side} side"})

    legacy_msgs = [_clean(e.get("text", "")) for e in legacy.get("events", [])
                   if e.get("type") == "validation" and e.get("selector") == DOM_ALERT_SELECTOR]
    modern_msgs = [_clean(e.get("text", "")) for e in modern.get("events", [])
                   if e.get("type") == "validation" and e.get("selector") == DOM_ALERT_SELECTOR]
    if not legacy_msgs and not modern_msgs:
        passed += 1
        total += 1
    else:
        absorb(_diff_values(legacy_msgs, modern_msgs, "$.validationMessages",
                            "missing-validation-message", "missing-validation-message"))

    scenario = legacy.get("scenarioName", "")
    if scenario == "scenario_auth_bridge":
        absorb(_diff_auth_bridge(legacy_net, modern_net))
        absorb(_diff_bearer_draft(legacy_net, modern_net))
        absorb(_diff_heartbeat(legacy_net, modern_net))
        absorb(_diff_anti_cache(legacy_net, modern_net))
    elif scenario == "scenario_governance":
        absorb(_diff_governance_stages(legacy_net, modern_net))
        absorb(_diff_anti_cache(legacy_net, modern_net))

    absorb(_diff_values(_normalize(legacy.get("finalStateSnapshot", {})),
                        _normalize(modern.get("finalStateSnapshot", {})),
                        "$.finalState", "payload-mismatch", "missing-state"))

    match_percentage = round(100 * passed / total, 2) if total else 100.0

    def ref(path: Path) -> str:
        try:
            return path.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            return str(path)

    report = {
        "legacyTraceRef": ref(legacy_file),
        "modernTraceRef": ref(modern_file),
        "matchPercentage": match_percentage,
        "discrepancies": discrepancies,
    }
    try:
        from jsonschema import Draft202012Validator

        schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors(report))
        if errors:
            raise ValueError(f"parity report failed schema validation: {errors[0].message}")
    except ImportError:
        pass
    out = Path(output_path) if output_path else REPORT_DIR / f"parity_{legacy_file.stem}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report, passed, total
