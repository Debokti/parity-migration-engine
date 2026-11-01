"""Secure repair loop driven by verifier diffs via Baseten enclave."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from config import BASETEN_MODEL  # noqa: E402

SYSTEM_PROMPT = (
    "You are a secure, private enterprise repair agent running in a Baseten enclave. "
    "Analyze the provided deterministic Playwright diff report and the failing Angular component. "
    "Provide the minimal TypeScript code changes required to make the component's state, DOM selectors, "
    "validations, and payloads match the legacy behavior."
)

FORMAT_INSTRUCTION = (
    "Respond with the minimal fix as a unified diff in a ```diff fenced block against the component "
    "above (with ---/+++ headers and @@ hunks using the component's real line numbers), "
    "then a one-paragraph explanation. Fix the root cause in state or logic; do not suppress, "
    "gate, or hide validation messages to match counts. Pre-run seed state is authoritative for "
    "fixtures: never copy post-run mutated values into them. When the missing message is produced "
    "server-side at submit time, parse it from the submit response and display it verbatim "
    "(deduped against local messages) instead of changing fixtures."
)
ROOT = Path(__file__).resolve().parents[2]


def _extract_diff(text: str) -> str | None:
    match = re.search(r"```diff\s*\n(.*?)```", text, re.DOTALL)
    return match.group(1).strip("\n") if match else None


def _parse_hunks(diff: str) -> list[tuple[int, list[tuple[str, str]]]]:
    hunks: list[tuple[int, list[tuple[str, str]]]] = []
    current: tuple[int, list[tuple[str, str]]] | None = None
    for line in diff.splitlines():
        header = re.match(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@", line)
        if header:
            current = (int(header.group(1)) - 1, [])
            hunks.append(current)
            continue
        if current is None:
            continue
        if line.startswith("\\"):
            continue
        kind, content = (line[:1], line[1:]) if line else (" ", "")
        if kind not in (" ", "-", "+"):
            raise ValueError(f"unrecognized diff line: {line!r}")
        current[1].append((kind, content))
    return [(start, ops) for start, ops in hunks if ops]


def _apply_diff(component_path: Path, diff: str) -> None:
    original = component_path.read_text(encoding="utf-8").splitlines()
    hunks = _parse_hunks(diff)
    if not hunks:
        raise ValueError("no hunks found in diff; refusing write-back")
    result: list[str] = []
    index = 0
    for claimed, ops in hunks:
        matchable = [content for kind, content in ops if kind in (" ", "-")]
        if matchable:
            width = len(matchable)
            candidates = [i for i in range(index, len(original) - width + 1)
                          if original[i:i + width] == matchable]
            if not candidates:
                raise ValueError("diff hunk does not match component content; refusing write-back")
            if len(candidates) > 1:
                if claimed < index or claimed + width > len(original) \
                        or original[claimed:claimed + width] != matchable:
                    raise ValueError("diff hunk is ambiguous; refusing write-back")
                pos = claimed
            else:
                pos = candidates[0]
        else:
            pos = min(max(claimed, index), len(original))
        result.extend(original[index:pos])
        index = pos
        for kind, content in ops:
            if kind in (" ", ""):
                index += 1
                result.append(content)
            elif kind == "-":
                index += 1
            else:
                result.append(content)
    result.extend(original[index:])
    text = "\n".join(result)
    if not text.endswith("\n"):
        text += "\n"
    component_path.write_text(text, encoding="utf-8")


def _legacy_state_context(diff_report_path: Path) -> str:
    try:
        import json as _json

        report = _json.loads(diff_report_path.read_text(encoding="utf-8"))
        ref = report.get("legacyTraceRef", "")
        trace_file = (ROOT / ref) if ref and not Path(ref).is_absolute() else Path(ref)
        trace = _json.loads(trace_file.read_text(encoding="utf-8"))
        requests = trace.get("finalStateSnapshot", {}).get("requests", [])
        refs = [(r.get("ref"), r.get("requestedAmount"), r.get("currency")) for r in requests]
        seed_block = ""
        try:
            spec = _json.loads((ROOT / "artifacts" / "specs" / "drawdown-spec.json").read_text(encoding="utf-8"))
            for table in spec.get("preconditions", {}).get("seededData", []):
                if table.get("table") == "invoices":
                    seed = [{k: r.get(k) for k in ("ref", "status", "currency", "amount", "financedAmount")}
                            for r in table.get("rows", [])]
                    seed_block = f"Seed (pre-run) invoice state: {_json.dumps(seed)}\n"
        except (OSError, ValueError):
            pass
        return (f"Legacy backend ground-truth state ({ref}):\n{seed_block}"
                f"Post-run requests(ref, amount, currency): {_json.dumps(refs)}\n"
                f"(Post-run per-invoice financed amounts are asserted by the diff, not fixtures.)")
    except (OSError, ValueError, KeyError, AttributeError):
        return ""


def generate_repair(
    diff_report_path: str | Path,
    failed_component_path: str | Path,
    write_back: bool = False,
) -> str:
    diff_file = Path(diff_report_path)
    diff = diff_file.read_text(encoding="utf-8")
    component = Path(failed_component_path).read_text(encoding="utf-8")
    ground_truth = _legacy_state_context(diff_file)
    ground_block = f"\n\n{ground_truth}" if ground_truth else ""
    response = config.baseten_client.chat.completions.create(
        model=BASETEN_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Playwright diff report:\n{diff}\n\nFailing Angular component:\n{component}"
                           f"{ground_block}\n\n{FORMAT_INSTRUCTION}",
            },
        ],
    )
    repair = response.choices[0].message.content or ""
    if write_back:
        patch = _extract_diff(repair)
        if patch is None:
            raise ValueError("no ```diff block found in repair response; refusing write-back")
        _apply_diff(Path(failed_component_path), patch)
    return repair
