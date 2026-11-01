"""LLM-based BehaviorSpec extraction from legacy source and golden traces."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from adapters.jsp_adapter import JspAdapter  # noqa: E402
from config import PRIMARY_MODEL  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "artifacts" / "specs" / "drawdown-spec.json"

SYSTEM_PROMPT = (
    "You are an expert enterprise architect migrating a legacy JSP application. "
    "Analyze the provided Java source code and the Playwright execution trace. "
    "Extract the complete business logic, validations, state mutations, and API payloads. "
    "You must output strictly valid JSON conforming exactly to the provided BehaviorSpec schema."
)


def extract_behavior_spec(
    trace_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> dict:
    adapter = JspAdapter()
    response = config.meta_client.chat.completions.create(
        model=PRIMARY_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "BehaviorSpec JSON schema:\n"
                    f"{adapter.load_schema()}\n\n"
                    f"Legacy context:\n{adapter.build_context(trace_path)}"
                ),
            },
        ],
        response_format={"type": "json_object"},
    )
    spec = json.loads(response.choices[0].message.content or "{}")
    try:
        from jsonschema import Draft202012Validator

        errors = list(Draft202012Validator(json.loads(adapter.load_schema())).iter_errors(spec))
        if errors:
            raise ValueError(f"LLM output failed BehaviorSpec validation: {errors[0].message}")
    except ImportError:
        pass
    out = Path(output_path) if output_path else DEFAULT_OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return spec


def main() -> int:
    spec = extract_behavior_spec()
    print(f"BehaviorSpec extracted to {DEFAULT_OUTPUT} ({len(spec.get('steps', []))} steps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
