"""Parity Control Center: browser GUI + Architect Chat for parity_cli.

Exposes every parity_cli.py subcommand over JSON REST and serves an embedded
single-page dashboard. Standard library only (http.server) — zero new Python
dependencies. Never reads, logs, or serves API keys.
"""

from __future__ import annotations

import io
import json
import sys
import traceback
import webbrowser
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from parity_cli import (  # noqa: E402
    ROOT,
    ask_question,
    digest_golden_trace,
    load_ask_context,
    load_coexistence_evidence,
    report_totals_line,
)

SCENARIOS = [f"scenario_{i}" for i in range(1, 7)]
PLACEHOLDERS = (
    ("capture", "Capture golden traces from the legacy application."),
    ("spec", "Extract a BehaviorSpec from source and traces."),
    ("prove", "Replay traces and produce a deterministic parity report."),
)
MAX_PREVIEW_CHARS = 8000


def _provider_info() -> dict:
    import config

    return {
        "provider": config.provider_name(),
        "primaryModel": config.PRIMARY_MODEL,
        "fireworksModel": config.FIREWORKS_MODEL,
        "basetenModel": config.BASETEN_MODEL,
    }


def _run_verify_one(stem: str) -> dict:
    """Mirror of the `verify` pipeline in parity_cli.main()."""
    from verifier.parity_differ import REPORT_DIR, diff_traces
    from verifier.trace_replayer import REPLAY_DIR, replay_trace

    if stem.endswith(".json"):
        stem = stem[: -len(".json")]
    if stem.startswith("replay_"):
        stem = stem[len("replay_"):]
    golden = ROOT / "artifacts" / "golden-traces" / f"{stem}.json"
    if not golden.is_file():
        return {"status": "ERROR", "scenario": stem,
                "error": f"golden trace not found: {golden}"}
    replay_path = replay_trace(golden, REPLAY_DIR / f"replay_{stem}.json")
    report, passed, total = diff_traces(golden, replay_path, REPORT_DIR / f"parity_{stem}.json")
    status = "PASS" if total > 0 and report["matchPercentage"] == 100 else "FAIL"
    return {
        "status": status,
        "scenario": stem,
        "matchPercentage": report["matchPercentage"],
        "passed": passed,
        "total": total,
        "discrepancies": report["discrepancies"],
        "replayPath": str(replay_path),
        "reportPath": str(REPORT_DIR / f"parity_{stem}.json"),
        "report": report,
        "replay": json.loads(Path(replay_path).read_text(encoding="utf-8")),
    }


def _api_context() -> dict:
    spec_text, summaries = load_ask_context()
    traces_dir = ROOT / "artifacts" / "golden-traces"
    reports_dir = ROOT / "artifacts" / "reports"
    return {
        "provider": _provider_info(),
        "specText": spec_text,
        "summaries": summaries,
        "totals": report_totals_line(summaries),
        "digests": {stem: digest_golden_trace(stem) for stem in SCENARIOS},
        "evidence": load_coexistence_evidence(),
        "traces": [s for s in SCENARIOS if (traces_dir / f"{s}.json").is_file()],
        "reports": sorted(p.name for p in reports_dir.glob("parity_scenario_*.json")),
        "placeholders": [
            {"name": name, "help": help_text, "status": "not configured yet"}
            for name, help_text in PLACEHOLDERS
        ],
    }


def _resolve_path(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None
    p = Path(raw.strip())
    if not p.is_absolute():
        p = ROOT / p
    return str(p)


def _api_ask(payload: dict) -> dict:
    question = (payload.get("question") or "").strip()
    if not question:
        raise ValueError("question is required")
    answer = ask_question(
        question,
        spec_path=_resolve_path(payload.get("spec")),
        reports_dir=_resolve_path(payload.get("reports")),
        traces_dir=_resolve_path(payload.get("traces")),
    )
    return {"answer": answer, "provider": _provider_info()}


def _api_extract(payload: dict) -> dict:
    from agents.spec_extractor import DEFAULT_OUTPUT, extract_behavior_spec

    trace = _resolve_path(payload.get("trace"))
    output = _resolve_path(payload.get("output"))
    log = io.StringIO()
    with redirect_stdout(log), redirect_stderr(log):
        spec = extract_behavior_spec(trace_path=trace, output_path=output)
    out_file = Path(output) if output else Path(DEFAULT_OUTPUT)
    if not out_file.is_absolute():
        out_file = ROOT / out_file
    return {"spec": spec, "output": str(out_file), "log": log.getvalue()}


def _api_migrate(payload: dict) -> dict:
    from agents.angular_generator import generate_components

    spec = _resolve_path(payload.get("spec"))
    output = _resolve_path(payload.get("output"))
    log = io.StringIO()
    with redirect_stdout(log), redirect_stderr(log):
        written = generate_components(spec_path=spec, output_dir=output)
    files = []
    for path in written:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            text = f"(unreadable: {exc})"
        if len(text) > MAX_PREVIEW_CHARS:
            text = text[:MAX_PREVIEW_CHARS] + "\n…(truncated)"
        files.append({"path": str(path), "preview": text})
    return {"files": files, "log": log.getvalue()}


def _api_verify(payload: dict) -> dict:
    if payload.get("all"):
        return {"results": [_run_verify_one(stem) for stem in SCENARIOS]}
    scenario = (payload.get("scenario") or "").strip()
    if not scenario:
        raise ValueError("scenario is required (or all=true)")
    return _run_verify_one(scenario)


def _api_repair(payload: dict) -> dict:
    from agents.repair_agent import generate_repair

    diff = _resolve_path(payload.get("diff")) or ""
    component = _resolve_path(payload.get("component")) or ""
    if not diff or not component:
        raise ValueError("diff and component paths are required")
    write_back = bool(payload.get("write_back"))
    result = generate_repair(diff, component, write_back=write_back)
    return {"repair": result, "writeBack": write_back, "component": component}


class _Handler(BaseHTTPRequestHandler):
    server_version = "ParityControlCenter/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("gui: " + fmt % args + "\n")

    def _send_json(self, obj: object, status: int = 200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/":
                body = INDEX_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/api/cli/context":
                self._send_json(_api_context())
            else:
                self._send_json({"error": "not found"}, 404)
        except Exception as exc:  # noqa: BLE001 - local tool; report, never leak keys
            traceback.print_exc()
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def do_POST(self) -> None:
        routes = {
            "/api/cli/ask": _api_ask,
            "/api/cli/extract": _api_extract,
            "/api/cli/migrate": _api_migrate,
            "/api/cli/verify": _api_verify,
            "/api/cli/repair": _api_repair,
        }
        path = urlparse(self.path).path
        handler = routes.get(path)
        if handler is None:
            self._send_json({"error": "not found"}, 404)
            return
        try:
            payload = self._read_json()
        except ValueError:
            self._send_json({"error": "invalid JSON body"}, 400)
            return
        try:
            self._send_json(handler(payload))
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
        except Exception as exc:  # noqa: BLE001 - local tool; report, never leak keys
            traceback.print_exc()
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)


class _GuiHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True


def run_gui_server(host: str = "127.0.0.1", port: int = 8501, open_browser: bool = False) -> str:
    url = f"http://{host}:{port}"
    server = _GuiHTTPServer((host, port), _Handler)
    print(f"Parity Control Center: {url}", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return url


INDEX_HTML = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Parity Control Center</title>
<style>
:root { --bg:#0d1117; --panel:#161b22; --line:#30363d; --fg:#e6edf3; --mut:#8b949e;
  --acc:#58a6ff; --ok:#3fb950; --bad:#f85149; --warn:#d29922; --chip:#21262d; }
html[data-theme="light"] { --bg:#f6f8fa; --panel:#ffffff; --line:#d0d7de; --fg:#1f2328;
  --mut:#59636e; --acc:#0969da; --ok:#1a7f37; --bad:#cf222e; --warn:#9a6700; --chip:#eaeef2; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:14px/1.5 system-ui,sans-serif; }
header { display:flex; align-items:center; gap:12px; padding:10px 16px; background:var(--panel);
  border-bottom:1px solid var(--line); position:sticky; top:0; z-index:5; flex-wrap:wrap; }
header h1 { font-size:17px; margin:0; }
#provBadge { font-size:12px; color:var(--mut); }
#themeBtn { margin-left:auto; }
nav.tabs { display:flex; gap:4px; padding:8px 16px 0; flex-wrap:wrap; }
nav.tabs button { background:none; border:1px solid transparent; border-bottom:none; color:var(--mut);
  padding:8px 14px; cursor:pointer; font-size:14px; border-radius:8px 8px 0 0; }
nav.tabs button.active { color:var(--fg); background:var(--panel); border-color:var(--line); }
main { padding:16px; max-width:1100px; }
section.view { display:none; background:var(--panel); border:1px solid var(--line);
  border-radius:0 8px 8px 8px; padding:16px; }
section.view.active { display:block; }
label { display:block; margin:10px 0 4px; color:var(--mut); font-size:12px; }
input[type=text], select, textarea { width:100%; background:var(--bg); color:var(--fg);
  border:1px solid var(--line); border-radius:6px; padding:8px; font-size:13px; }
textarea { min-height:70px; resize:vertical; }
button.run, button.sendbtn { background:var(--acc); color:#fff; border:none; border-radius:6px;
  padding:9px 16px; margin-top:12px; cursor:pointer; font-size:14px; }
button.ghost { background:var(--chip); color:var(--fg); border:1px solid var(--line);
  border-radius:6px; padding:6px 12px; cursor:pointer; }
button:disabled { opacity:.5; cursor:wait; }
pre, .log { background:var(--bg); border:1px solid var(--line); border-radius:6px; padding:10px;
  overflow:auto; max-height:420px; font-size:12px; white-space:pre-wrap; }
details { margin-top:10px; border:1px solid var(--line); border-radius:6px; padding:8px 10px; }
summary { cursor:pointer; }
#chatLog { border:1px solid var(--line); border-radius:6px; padding:10px; min-height:220px;
  max-height:420px; overflow:auto; margin-bottom:10px; }
.msg { margin:8px 0; padding:8px 10px; border-radius:6px; }
.msg.q { background:var(--chip); }
.msg.a { border:1px solid var(--line); white-space:pre-wrap; }
.chips { display:flex; gap:8px; flex-wrap:wrap; margin:8px 0; }
.chips button { background:var(--chip); color:var(--fg); border:1px solid var(--line);
  border-radius:16px; padding:5px 12px; cursor:pointer; font-size:12px; }
.badge { display:inline-block; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600; }
.badge.pass { background:var(--ok); color:#fff; }
.badge.fail { background:var(--bad); color:#fff; }
.badge.err { background:var(--warn); color:#000; }
.score { border:1px solid var(--line); border-radius:6px; padding:10px; margin:8px 0; }
.spin { display:inline-block; width:14px; height:14px; border:2px solid var(--line);
  border-top-color:var(--acc); border-radius:50%; animation:sp 0.8s linear infinite;
  vertical-align:-2px; margin-right:6px; }
@keyframes sp { to { transform:rotate(360deg); } }
.row { display:flex; gap:10px; align-items:end; flex-wrap:wrap; }
.row > div { flex:1; min-width:200px; }
ul.plain { list-style:none; padding:0; }
ul.plain li { padding:4px 0; border-bottom:1px solid var(--line); font-size:13px; }
</style>
</head>
<body>
<header>
<h1>Parity Control Center</h1>
<span id="provBadge">loading provider…</span>
<button id="themeBtn" class="ghost">Light / Dark</button>
</header>
<nav class="tabs" id="tabs">
<button data-v="chat" class="active">Architect Chat</button>
<button data-v="verify">Verify</button>
<button data-v="extract">Extract</button>
<button data-v="migrate">Migrate</button>
<button data-v="repair">Repair</button>
<button data-v="context">Context</button>
</nav>
<main>
<section class="view active" id="v-chat">
<div id="chatLog"><div class="msg a">Ask about JSESSIONID/Bearer sync, MFE coexistence, anti-cache, 4-Eyes governance, or coverage. Answers are grounded in the BehaviorSpec, parity reports, and golden-trace digests.</div></div>
<div class="chips" id="chips">
<button>How does JSESSIONID &lt;-&gt; Bearer sync work?</button>
<button>Summarize parity across scenarios 1-6</button>
<button>Explain the 4-Eyes Maker/Checker governance proof</button>
</div>
<textarea id="q" placeholder="Type your architecture question…"></textarea>
<div class="row">
<div><label>--spec path (optional)</label><input type="text" id="qSpec" placeholder="artifacts/specs/drawdown-spec.json"></div>
<div><label>--reports dir (optional)</label><input type="text" id="qReports" placeholder="artifacts/reports"></div>
<div><label>--traces dir (optional)</label><input type="text" id="qTraces" placeholder="artifacts/golden-traces"></div>
</div>
<button class="sendbtn" id="sendBtn">Send</button>
</section>
<section class="view" id="v-verify">
<div class="row">
<div><label>--scenario</label><select id="vScenario">
<option>scenario_1</option><option>scenario_2</option><option>scenario_3</option>
<option>scenario_4</option><option>scenario_5</option><option>scenario_6</option>
</select></div>
<div><label>&nbsp;</label><button class="run" id="verifyBtn">Run Verify (Playwright)</button>
<button class="ghost" id="verifyAllBtn">Verify All Scenarios</button></div>
</div>
<div id="scores"></div>
</section>
<section class="view" id="v-extract">
<div class="row">
<div><label>--trace</label><select id="xTrace"></select></div>
<div><label>--trace custom path (overrides dropdown)</label><input type="text" id="xTraceCustom" placeholder=""></div>
</div>
<label>--output</label><input type="text" id="xOut" value="artifacts/specs/drawdown-spec.json">
<button class="run" id="extractBtn">Run Extract (Meta muse-spark-1.3)</button>
<h4>Console</h4><pre class="log" id="xLog">(no run yet)</pre>
<h4>BehaviorSpec</h4><pre id="xSpec">(no run yet)</pre>
</section>
<section class="view" id="v-migrate">
<label>--spec</label><input type="text" id="mSpec" value="artifacts/specs/drawdown-spec.json">
<label>--output</label><input type="text" id="mOut" value="target-angular/src/app/drawdown">
<button class="run" id="migrateBtn">Run Migrate (Fireworks muse-spark-open)</button>
<h4>Console</h4><pre class="log" id="mLog">(no run yet)</pre>
<h4>Generated files</h4><ul class="plain" id="mFiles"></ul>
<h4>Preview</h4><pre id="mPreview">(select a run first)</pre>
</section>
<section class="view" id="v-repair">
<label>--diff (parity report)</label><select id="rDiff"></select>
<label>--component</label><input type="text" id="rComp" value="target-angular/src/app/drawdown/drawdown.component.ts">
<label><input type="checkbox" id="rWrite"> --write-back (write repair into the component file)</label>
<button class="run" id="repairBtn">Generate Repair (Baseten Enclave)</button>
<h4>TypeScript repair</h4><pre id="rOut">(no run yet)</pre>
</section>
<section class="view" id="v-context">
<button class="ghost" id="ctxBtn">Refresh live context</button>
<h4>Totals</h4><pre id="cTotals">(loading…)</pre>
<h4>Scenario summaries</h4><ul class="plain" id="cSum"></ul>
<h4>Golden-trace digests</h4><div id="cDig"></div>
<h4>Coexistence evidence</h4><pre id="cEv"></pre>
<h4>Placeholder subcommands</h4><ul class="plain" id="cPh"></ul>
</section>
</main>
<script>
"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
async function post(path, body) {
  const r = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body || {})});
  const j = await r.json().catch(() => ({error: "bad response " + r.status}));
  if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
  return j;
}
document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll("#tabs button").forEach((x) => x.classList.remove("active"));
  document.querySelectorAll("section.view").forEach((x) => x.classList.remove("active"));
  b.classList.add("active");
  $("v-" + b.dataset.v).classList.add("active");
}));
$("themeBtn").addEventListener("click", () => {
  const h = document.documentElement;
  h.dataset.theme = h.dataset.theme === "dark" ? "light" : "dark";
});
function spin(el, on, label) {
  if (on) { el.dataset.t = el.textContent; el.disabled = true;
    el.innerHTML = '<span class="spin"></span>' + esc(label || "Working…"); }
  else { el.disabled = false; el.textContent = el.dataset.t || "Done"; }
}
async function sendChat(q) {
  const log = $("chatLog");
  log.insertAdjacentHTML("beforeend", '<div class="msg q">' + esc(q) + "</div>");
  const wait = document.createElement("div");
  wait.className = "msg a"; wait.innerHTML = '<span class="spin"></span>thinking…';
  log.appendChild(wait); log.scrollTop = log.scrollHeight;
  try {
    const j = await post("/api/cli/ask", {question: q, spec: $("qSpec").value.trim(),
      reports: $("qReports").value.trim(), traces: $("qTraces").value.trim()});
    wait.textContent = j.answer;
  } catch (e) { wait.textContent = "Error: " + e.message; }
  log.scrollTop = log.scrollHeight;
}
$("sendBtn").addEventListener("click", () => {
  const q = $("q").value.trim(); if (!q) return; $("q").value = ""; sendChat(q);
});
document.querySelectorAll("#chips button").forEach((b) =>
  b.addEventListener("click", () => sendChat(b.textContent)));
function scoreCard(r) {
  const cls = r.status === "PASS" ? "pass" : (r.status === "FAIL" ? "fail" : "err");
  const head = r.status === "ERROR" ? r.scenario + ": " + esc(r.error || "error")
    : r.scenario + ": " + r.matchPercentage + "% (" + r.passed + "/" + r.total +
      " checks), " + (r.discrepancies || []).length + " discrepancies";
  let h = '<div class="score"><span class="badge ' + cls + '">' + r.status + "</span> " + esc(head);
  h += "<br><small>" + esc(r.replayPath || "") + "<br>" + esc(r.reportPath || "") + "</small>";
  if (r.report) h += "<details><summary>parity report</summary><pre>" +
    esc(JSON.stringify(r.report, null, 2)) + "</pre></details>";
  if (r.replay) h += "<details><summary>replay trace</summary><pre>" +
    esc(JSON.stringify(r.replay).slice(0, 20000)) + "</pre></details>";
  return h + "</div>";
}
async function runVerify(all) {
  spin($("verifyBtn"), true, all ? "Verifying all…" : "Verifying…");
  $("verifyAllBtn").disabled = true;
  try {
    const j = await post("/api/cli/verify", all ? {all: true} : {scenario: $("vScenario").value});
    const list = j.results || [j];
    $("scores").innerHTML = list.map(scoreCard).join("");
  } catch (e) { $("scores").innerHTML = '<div class="score">Error: ' + esc(e.message) + "</div>"; }
  spin($("verifyBtn"), false); $("verifyAllBtn").disabled = false;
}
$("verifyBtn").addEventListener("click", () => runVerify(false));
$("verifyAllBtn").addEventListener("click", () => runVerify(true));
$("extractBtn").addEventListener("click", async () => {
  spin($("extractBtn"), true, "Extracting…");
  try {
    const custom = $("xTraceCustom").value.trim();
    const j = await post("/api/cli/extract", {trace: custom || $("xTrace").value,
      output: $("xOut").value.trim()});
    $("xLog").textContent = j.log || "(no console output)";
    $("xSpec").textContent = JSON.stringify(j.spec, null, 2);
  } catch (e) { $("xLog").textContent = "Error: " + e.message; }
  spin($("extractBtn"), false);
});
$("migrateBtn").addEventListener("click", async () => {
  spin($("migrateBtn"), true, "Migrating…");
  try {
    const j = await post("/api/cli/migrate", {spec: $("mSpec").value.trim(),
      output: $("mOut").value.trim()});
    $("mLog").textContent = j.log || "(no console output)";
    $("mFiles").innerHTML = (j.files || []).map((f) => "<li>" + esc(f.path) + "</li>").join("");
    $("mPreview").textContent = ((j.files || [])[0] || {}).preview || "(no files)";
  } catch (e) { $("mLog").textContent = "Error: " + e.message; }
  spin($("migrateBtn"), false);
});
$("repairBtn").addEventListener("click", async () => {
  spin($("repairBtn"), true, "Repairing…");
  try {
    const j = await post("/api/cli/repair", {diff: $("rDiff").value, component: $("rComp").value.trim(),
      write_back: $("rWrite").checked});
    $("rOut").textContent = (j.writeBack ? "[wrote back to " + j.component + "]\\n\\n" : "") + j.repair;
  } catch (e) { $("rOut").textContent = "Error: " + e.message; }
  spin($("repairBtn"), false);
});
async function refreshContext() {
  try {
    const j = await fetch("/api/cli/context").then((r) => r.json());
    const p = j.provider || {};
    $("provBadge").textContent = "provider=" + p.provider + " primary=" + p.primaryModel +
      " fireworks=" + p.fireworksModel + " baseten=" + p.basetenModel;
    $("cTotals").textContent = j.totals || "(no totals)";
    $("cSum").innerHTML = (j.summaries || []).map((s) => "<li>" + esc(s) + "</li>").join("");
    $("cDig").innerHTML = Object.keys(j.digests || {}).map((k) =>
      "<details><summary>" + esc(k) + "</summary><pre>" + esc(j.digests[k]) + "</pre></details>").join("");
    $("cEv").textContent = j.evidence || "";
    $("cPh").innerHTML = (j.placeholders || []).map((x) =>
      "<li>" + esc(x.name) + " — " + esc(x.help) + " [" + esc(x.status) + "]</li>").join("");
    $("xTrace").innerHTML = (j.traces || []).map((t) =>
      "<option>artifacts/golden-traces/" + t + ".json</option>").join("");
    $("rDiff").innerHTML = (j.reports || []).map((r) =>
      "<option>artifacts/reports/" + r + "</option>").join("");
  } catch (e) { $("cTotals").textContent = "Error: " + e.message; }
}
$("ctxBtn").addEventListener("click", refreshContext);
refreshContext();
</script>
</body>
</html>
"""
