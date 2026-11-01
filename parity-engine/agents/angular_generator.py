"""Fast Angular scaffolding from a BehaviorSpec via Fireworks AI.

Phase B: emits the corporate-portal Drawdown MFE (auth bridge, AG Grid
registers, Maker/Checker 4-eyes panel, federation mount hook, unit tests)
instead of the bare workflow component.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from config import FIREWORKS_MODEL  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = ROOT / "artifacts" / "specs" / "drawdown-spec.json"
DEFAULT_OUTPUT = ROOT / "target-angular" / "src" / "app" / "drawdown"

SYSTEM_PROMPT = (
    "You are a senior Angular developer scaffolding a Phase B enterprise migration from a legacy JSP application. "
    "Generate a reactive, signal-based Angular 17 (@angular/core ^17.3.0) Drawdown MFE with this exact architecture. "
    "1) Business rules from the BehaviorSpec: 85% advance cap across selected eligible invoices "
    "(maxAdvanceable = sum(invoice amounts) * 0.85), allowed currencies USD/EUR/GBP, allowed tenors 30/60/90, "
    "beneficiary codes matching ^BEN-[A-Z]{2}-[0-9]{3}$, required terms acknowledgment, discountFee = "
    "amount * 0.06 * tenorDays / 360 with half-up 2-decimal rounding, flat 50.00 processing fee. "
    "2) Corporate portal shell: deep navy (#003366) banner titled 'Commercial Supply Chain Finance Portal' with "
    "subtitle 'Angular Federated MFE Module | Release 2.4', actor switcher (data-testid='actor-switcher' with "
    "maker-1/checker-1/checker-2), auth-bridge status badge (data-testid='auth-bridge-status'), left navigation "
    "menu, breadcrumb 'Home / Drawdown Workflow', Supplier Program Summary card, dense Verdana 11px enterprise "
    "form and table styling. "
    "3) AG Grid Community (ag-grid-angular v31 AgGridModule, ag-theme-alpine, domLayout autoHeight) for the "
    "Invoice Register with a per-row checkbox cell renderer exposing data-testid='invoice-<ref>', and for the "
    "Request History table. "
    "4) Session<->Bearer auth bridge: handshake GET /api/v1/auth/bridge (or adopt window.__PARITY_MFE_CONTEXT__ / "
    "'parity:auth-handshake' when embedded), send Authorization Bearer plus X-Actor-Id/X-Actor-Role plus "
    "Cache-Control no-cache/no-store/must-revalidate plus Pragma no-cache with withCredentials on /api/v1/*, "
    "and poll POST /api/v1/auth/heartbeat. "
    "5) Role-gated 4-eyes panel: Amend form for MAKER_1 (PUT /api/v1/requests/{ref}/amend), 1st Checker "
    "approve/reject for CHECKER_1 and 2nd Checker approve/reject for CHECKER_2 "
    "(POST /api/v1/requests/{ref}/checker1|checker2 with action and rejectionReason). "
    "6) Module federation: webpack.mf.config.js (ModuleFederationPlugin name northstarDrawdown, remoteEntry.js, "
    "shared Angular singletons), a <northstar-drawdown-mfe> custom element, and window.mountNorthstarDrawdownMfe, "
    "working both standalone and inside the legacy MFE popup. "
    "7) A drawdown.component.spec.ts Karma/Jasmine suite covering the 85% cap, fee math, validation messages, "
    "auth bridge headers, and Maker->Checker1->Checker2 flows. "
    "Preserve the exact DOM element IDs and data-testid attributes (#amount, #currency, #tenorDays, "
    "#beneficiaryCode, #ackTerms, #validation-errors, #confirmation, invoice-<ref>, submit-invoices, "
    "submit-drawdown, submit-attachment, sync-draft, submit-review, attachment-list, *-step sections) with "
    "identical input bindings, network payloads, and validation message formats so deterministic Playwright "
    "traces replay unchanged. "
    "Output strictly valid JSON: an object mapping each relative file path to its complete file content."
)


def _parse_files(content: str) -> dict[str, str]:
    try:
        files = json.loads(content)
    except ValueError:
        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
        if not match:
            raise ValueError("Fireworks output was not a JSON file map")
        files = json.loads(match.group(1))
    if not isinstance(files, dict) or not files:
        raise ValueError("Fireworks output was not a JSON file map")
    return files


def generate_components(
    spec_path: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> list[Path]:
    spec_file = Path(spec_path) if spec_path else DEFAULT_SPEC
    spec = spec_file.read_text(encoding="utf-8")
    response = config.fireworks_client.chat.completions.create(
        model=FIREWORKS_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"BehaviorSpec:\n{spec}"},
        ],
        response_format={"type": "json_object"},
    )
    files = _parse_files(response.choices[0].message.content or "{}")
    out = Path(output_dir) if output_dir else DEFAULT_OUTPUT
    out.mkdir(parents=True, exist_ok=True)
    base = out.resolve()
    written = []
    for name, content in files.items():
        name = name.replace("\\", "/").lstrip("/")
        if name.startswith("src/app/drawdown/"):
            name = name[len("src/app/drawdown/"):]
        if not name or name in (".", ".."):
            raise ValueError(f"invalid generated file path: {name!r}")
        dest = (base / name).resolve()
        try:
            dest.relative_to(base)
        except ValueError:
            raise ValueError(f"refusing to write outside output dir: {name}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content if isinstance(content, str) else json.dumps(content, indent=2), encoding="utf-8")
        written.append(dest)
    return written


def main() -> int:
    written = generate_components()
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
