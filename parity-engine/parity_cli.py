"""Single entrypoint for the parity workflow."""

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent

ASK_SYSTEM_PROMPT = (
    "You are the Parity Migration Engine Architect. Answer questions directly, "
    "concisely, and accurately using the provided BehaviorSpec, parity reports, "
    "golden-trace digests, CLI command manifest, and build evidence. "
    "Focus your response specifically on the user's question rather than repeating "
    "unrelated architecture pillars. Do not hallucinate endpoints or numbers not in context. "
    "When asked about CLI commands or usage, refer to the Parity CLI subcommands."
)


def _scenario_counts(
    stem: str,
    traces_dir: Path,
    replays_dir: Path,
) -> tuple[int, int] | None:
    """Recompute passed/total checks offline via the locked differ (no servers)."""
    golden = traces_dir / f"{stem}.json"
    replay = replays_dir / f"replay_{stem}.json"
    if not golden.is_file() or not replay.is_file():
        return None
    try:
        from verifier.parity_differ import diff_traces
    except ImportError:
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="parity-ask-") as tmp:
            _, passed, total = diff_traces(golden, replay, Path(tmp) / f"parity_{stem}.json")
        return passed, total
    except Exception:
        return None


def load_ask_context(
    spec_path: str | Path | None = None,
    reports_dir: str | Path | None = None,
    traces_dir: str | Path | None = None,
    replays_dir: str | Path | None = None,
) -> tuple[str, list[str]]:
    spec_file = Path(spec_path) if spec_path else ROOT / "artifacts" / "specs" / "drawdown-spec.json"
    reports = Path(reports_dir) if reports_dir else ROOT / "artifacts" / "reports"
    traces = Path(traces_dir) if traces_dir else ROOT / "artifacts" / "golden-traces"
    replays = Path(replays_dir) if replays_dir else ROOT / "artifacts" / "replays"
    if spec_file.is_file():
        spec_text = spec_file.read_text(encoding="utf-8")
    else:
        spec_text = f"(missing BehaviorSpec: {spec_file} not found)"
    summaries: list[str] = []
    for stem in (f"scenario_{i}" for i in range(1, 7)):
        report_file = reports / f"parity_{stem}.json"
        if not report_file.is_file():
            summaries.append(f"{stem}: report not found")
            continue
        try:
            report = json.loads(report_file.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            summaries.append(f"{stem}: unreadable report ({exc})")
            continue
        match = report.get("matchPercentage", "?")
        discs = report.get("discrepancies", [])
        counts = _scenario_counts(stem, traces, replays)
        if counts is not None:
            summaries.append(f"{stem}: {match}% match, {counts[0]}/{counts[1]} checks, "
                             f"{len(discs)} discrepancies")
        else:
            summaries.append(f"{stem}: {match}% match, {len(discs)} discrepancies")
    return spec_text, summaries


def report_totals_line(summaries: list[str]) -> str | None:
    """Aggregate 'passed/total checks' fragments across scenario summaries."""
    passed = total = 0
    counted = 0
    for summary in summaries:
        match = re.search(r"(\d+)/(\d+) checks", summary)
        if match:
            passed += int(match.group(1))
            total += int(match.group(2))
            counted += 1
    if counted == 0:
        return None
    return f"total: {passed}/{total} checks across {counted} scenarios"


def _digest_body(body: object) -> str:
    if not isinstance(body, dict):
        return "" if body is None else str(body)[:80]
    parts: list[str] = []
    for key in ("ref", "status", "approvalStage", "createdBy", "amendedBy",
                "checker1By", "checker2By", "error", "valid", "actorId", "role",
                "reset", "invoiceRefs", "requestedAmount", "currency", "tenorDays"):
        if key not in body or body[key] is None:
            continue
        value = body[key]
        if key == "invoiceRefs" and isinstance(value, list):
            parts.append(f"invoiceRefs={value}")
        else:
            parts.append(f"{key}={value}")
    if isinstance(body.get("token"), str) and len(body["token"].split(".")) == 2:
        parts.append("token=<bearer body.signature>")
    if body.get("sessionId"):
        parts.append("sessionId=<session>")
    ttl = body.get("remainingTtlSeconds")
    if isinstance(ttl, (int, float)):
        parts.append(f"remainingTtlSeconds={'>0' if ttl > 0 else ttl}")
    return "{" + ", ".join(parts) + "}" if parts else ""


def digest_golden_trace(
    stem: str,
    traces_dir: str | Path | None = None,
) -> str:
    """Concise event digest of a golden trace (volatile token/session values redacted)."""
    traces = Path(traces_dir) if traces_dir else ROOT / "artifacts" / "golden-traces"
    path = traces / f"{stem}.json"
    if not path.is_file():
        return f"{stem}: golden trace not found ({path})"
    try:
        trace = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        return f"{stem}: unreadable golden trace ({exc})"
    lines = [f"{stem} ({trace.get('scenarioName', '?')}):"]
    for event in trace.get("events", []):
        if event.get("type") == "validation":
            lines.append(f"- validation [{event.get('selector', '?')}]: {event.get('text', '')}"[:220])
            continue
        if event.get("type") != "network":
            continue
        url_path = urlsplit(str(event.get("url", "")).split("?")[0]).path
        markers: list[str] = []
        req_headers = event.get("requestHeaders") or {}
        if str(req_headers.get("authorization", "")).startswith("Bearer "):
            markers.append("[Authorization: Bearer]")
        actor = req_headers.get("x-actor-id")
        role = req_headers.get("x-actor-role")
        if actor or role:
            markers.append(f"[actor {actor}/{role}]")
        resp_headers = event.get("responseHeaders") or {}
        cache = str(resp_headers.get("cache-control", ""))
        pragma = str(resp_headers.get("pragma", ""))
        if cache and pragma:
            markers.append(f"[Cache-Control: {cache[:56]}; Pragma: {pragma}]")
        body = _digest_body(event.get("responseBody"))
        req_body = event.get("requestPayload")
        req = f" req={_digest_body(req_body)}" if isinstance(req_body, dict) and req_body else ""
        line = f"- {event.get('method')} {url_path} {' '.join(markers)}-> {event.get('responseStatus')}"
        if body:
            line += f" {body}"
        lines.append((line + req)[:280])
    state = trace.get("finalStateSnapshot", {}) or {}
    reqs = state.get("requests", [])
    lines.append(f"- finalState: {len(reqs)} requests "
                 f"{[str(r.get('ref')) + ':' + str(r.get('approvalStage')) for r in reqs]}")
    return "\n".join(lines)


def load_coexistence_evidence(root: str | Path | None = None) -> str:
    """JaCoCo gate + Angular federation/AG Grid facts read from build files."""
    base = Path(root) if root else ROOT
    lines: list[str] = []
    pom = base / "legacy-jsp" / "pom.xml"
    try:
        text = pom.read_text(encoding="utf-8")
        version = re.search(r"jacoco-maven-plugin</artifactId><version>([^<]+)", text)
        minimums = sorted(set(re.findall(r"<minimum>(0\.\d+)</minimum>", text)))
        counters = sorted(set(re.findall(r"<counter>([A-Z]+)</counter>", text)))
        lines.append(f"legacy-jsp/pom.xml: jacoco-maven-plugin {version.group(1) if version else '?'}"
                     f", BUNDLE {'/'.join(counters)} COVEREDRATIO minimum {'/'.join(minimums)}")
    except OSError:
        lines.append(f"legacy-jsp/pom.xml: not found ({pom})")
    pkg = base / "target-angular" / "package.json"
    try:
        deps = json.loads(pkg.read_text(encoding="utf-8")).get("dependencies", {})
        lines.append("target-angular/package.json: "
                     + ", ".join(f"{k} {deps[k]}" for k in ("ag-grid-angular", "ag-grid-community") if k in deps))
    except (OSError, ValueError):
        lines.append(f"target-angular/package.json: not found ({pkg})")
    mf = base / "target-angular" / "webpack.mf.config.js"
    try:
        text = mf.read_text(encoding="utf-8")
        name = re.search(r"name:\s*'([^']+)'", text)
        filename = re.search(r"filename:\s*'([^']+)'", text)
        exposes = re.findall(r"'(\./[A-Za-z]+)'", text)
        lines.append(f"target-angular/webpack.mf.config.js: name={name.group(1) if name else '?'} "
                     f"filename={filename.group(1) if filename else '?'} exposes={sorted(set(exposes))}")
    except OSError:
        lines.append(f"target-angular/webpack.mf.config.js: not found ({mf})")
    mount = base / "target-angular" / "src" / "app" / "drawdown" / "mfe-mount.ts"
    try:
        text = mount.read_text(encoding="utf-8")
        element = re.search(r"MFE_ELEMENT_NAME\s*=\s*'([^']+)'", text)
        lines.append(f"mfe-mount.ts: element={element.group(1) if element else '?'} "
                     "mountNorthstarDrawdownMfe + iframe fallback to :4200")
    except OSError:
        lines.append(f"mfe-mount.ts: not found ({mount})")
    spec_ts = base / "target-angular" / "src" / "app" / "drawdown" / "drawdown.component.spec.ts"
    lines.append(f"drawdown.component.spec.ts: {'present' if spec_ts.is_file() else 'MISSING'}")
    return "\n".join(lines)


def ask_question(
    question: str,
    spec_path: str | Path | None = None,
    reports_dir: str | Path | None = None,
    traces_dir: str | Path | None = None,
) -> str:
    import config
    from config import PRIMARY_MODEL

    spec_text, summaries = load_ask_context(spec_path, reports_dir, traces_dir)
    totals = report_totals_line(summaries)
    traces = Path(traces_dir) if traces_dir else ROOT / "artifacts" / "golden-traces"
    digest5 = digest_golden_trace("scenario_5", traces)
    digest6 = digest_golden_trace("scenario_6", traces)
    evidence = load_coexistence_evidence()
    parts = [
        f"BehaviorSpec (drawdown-spec.json):\n{spec_text}\n",
        f"Parity reports:\n{chr(10).join(summaries)}",
    ]
    if totals:
        parts.append(totals)
    parts.append(f"Golden-trace digest scenario_5 (auth bridge + anti-cache + heartbeat):\n{digest5}\n")
    parts.append(f"Golden-trace digest scenario_6 (4-eyes governance):\n{digest6}\n")
    parts.append(f"Build evidence (coverage + federation + grid):\n{evidence}\n")
    cli_manifest = (
        "Parity CLI Command Manifest & Help:\n"
        "- Global Help: python parity-engine/parity_cli.py --help\n"
        "- Subcommands:\n"
        "  * extract: Extract BehaviorSpec from legacy trace (python parity-engine/parity_cli.py extract [--trace TRACE] [--output OUT])\n"
        "  * migrate: Generate modern Angular components (python parity-engine/parity_cli.py migrate [--spec SPEC] [--output OUT])\n"
        "  * verify: Deterministic Playwright parity replay & diff (python parity-engine/parity_cli.py verify --scenario SCENARIO)\n"
        "  * repair: Generate component repair from diff report (python parity-engine/parity_cli.py repair --diff DIFF --component COMP [--write-back])\n"
        "  * ask: Architecture Q&A grounded in spec and reports (python parity-engine/parity_cli.py ask \"QUESTION\")\n"
        "  * gui: Launch browser Control Center & Chat (python parity-engine/parity_cli.py gui [--host HOST] [--port PORT] [--open])\n"
    )
    parts.append(f"{cli_manifest}\n")
    parts.append(f"Question: {question}")
    response = config.meta_client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[
            {"role": "system", "content": ASK_SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(parts)},
        ],
    )
    return response.choices[0].message.content or ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="parity", description="Capture, specify, migrate, and prove application parity.")
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract", help="Extract a BehaviorSpec from legacy source and golden traces.")
    extract.add_argument("--trace", default=None, help="Golden trace file (default: artifacts/golden-traces/scenario_1.json).")
    extract.add_argument("--output", default=None, help="Output file (default: artifacts/specs/drawdown-spec.json).")
    migrate = sub.add_parser("migrate", help="Generate Angular components from a BehaviorSpec.")
    migrate.add_argument("--spec", default=None, help="BehaviorSpec file (default: artifacts/specs/drawdown-spec.json).")
    migrate.add_argument("--output", default=None, help="Output dir (default: target-angular/src/app/drawdown).")
    repair = sub.add_parser("repair", help="Generate a component repair from a Playwright diff report.")
    repair.add_argument("--diff", required=True, help="Deterministic Playwright diff report file.")
    repair.add_argument("--component", required=True, help="Failing Angular component file.")
    repair.add_argument("--write-back", action="store_true", help="Write the repair back to the component file.")
    verify = sub.add_parser("verify", help="Replay a golden trace against the modern app and diff the results.")
    verify.add_argument("--scenario", required=True, help="Scenario stem, e.g. scenario_1.")
    ask = sub.add_parser("ask", help="Ask architecture questions grounded in specs, traces, and reports.")
    ask.add_argument("question", help="Natural-language question about the parity engine.")
    ask.add_argument("--spec", default=None, help="BehaviorSpec file (default: artifacts/specs/drawdown-spec.json).")
    ask.add_argument("--reports", default=None, help="Parity reports dir (default: artifacts/reports).")
    ask.add_argument("--traces", default=None, help="Golden traces dir (default: artifacts/golden-traces).")
    gui = sub.add_parser("gui", help="Launch the browser-based Parity Control Center and Architect Chat GUI.")
    gui.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    gui.add_argument("--port", type=int, default=8501, help="Bind port (default: 8501).")
    gui.add_argument("--open", action="store_true", help="Open the GUI URL in the default browser.")
    args = parser.parse_args(argv)
    if args.command == "extract":
        from agents.spec_extractor import DEFAULT_OUTPUT, extract_behavior_spec

        extract_behavior_spec(trace_path=args.trace, output_path=args.output)
        print(f"BehaviorSpec extracted successfully to {args.output or DEFAULT_OUTPUT}")
        return 0
    if args.command == "migrate":
        from agents.angular_generator import DEFAULT_OUTPUT, generate_components

        written = generate_components(spec_path=args.spec, output_dir=args.output)
        print(f"Angular components generated successfully to {args.output or DEFAULT_OUTPUT}")
        for path in written:
            print(f"  {path}")
        return 0
    if args.command == "repair":
        from agents.repair_agent import generate_repair

        result = generate_repair(args.diff, args.component, write_back=args.write_back)
        if args.write_back:
            print(f"Repair written back to {args.component}")
        try:
            print(result)
        except UnicodeEncodeError:
            print(result.encode("ascii", "replace").decode("ascii"))
        return 0
    if args.command == "verify":
        from verifier.parity_differ import REPORT_DIR, diff_traces
        from verifier.trace_replayer import REPLAY_DIR, replay_trace

        stem = args.scenario
        if stem.endswith(".json"):
            stem = stem[: -len(".json")]
        if stem.startswith("replay_"):
            stem = stem[len("replay_"):]
        golden = ROOT / "artifacts" / "golden-traces" / f"{stem}.json"
        if not golden.is_file():
            print(f"golden trace not found: {golden}")
            return 1
        replay_path = replay_trace(golden, REPLAY_DIR / f"replay_{stem}.json")
        report, passed, total = diff_traces(golden, replay_path, REPORT_DIR / f"parity_{stem}.json")
        status = "PASS" if total > 0 and report["matchPercentage"] == 100 else "FAIL"
        print(f"{status} {stem}: {report['matchPercentage']}% ({passed}/{total} checks), "
              f"{len(report['discrepancies'])} discrepancies")
        print(f"replay: {replay_path}")
        print(f"report: {REPORT_DIR / f'parity_{stem}.json'}")
        return 0 if status == "PASS" else 1
    if args.command == "ask":
        try:
            answer = ask_question(args.question, spec_path=args.spec, reports_dir=args.reports,
                                  traces_dir=args.traces)
        except RuntimeError as exc:
            print(f"ask failed: {exc}")
            return 1
        try:
            print(answer)
        except UnicodeEncodeError:
            print(answer.encode("ascii", "replace").decode("ascii"))
        return 0
    if args.command == "gui":
        from gui_server import run_gui_server

        run_gui_server(host=args.host, port=args.port, open_browser=args.open)
        return 0
    print(f"{args.command} is not configured yet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
