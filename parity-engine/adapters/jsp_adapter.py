"""JSP source-and-trace context preparation for LLM extraction."""

from pathlib import Path
from typing import Any

from .base import SourceAdapter

ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILES = ["RuleEngine.java", "Invoice.java", "PageServlet.java"]
DEFAULT_TRACE = "artifacts/golden-traces/scenario_1.json"
SCHEMA_FILE = "contracts/schemas/behavior-spec.v1.json"


class JspAdapter(SourceAdapter):
    def __init__(self, root: Path = ROOT) -> None:
        self.root = root

    def load_source_context(self) -> str:
        parts = []
        for name in SOURCE_FILES:
            matches = sorted((self.root / "legacy-jsp" / "src").rglob(name))
            if not matches:
                raise FileNotFoundError(f"{name} not found under legacy-jsp/src")
            rel = matches[0].relative_to(self.root).as_posix()
            parts.append(f"===== {rel} =====\n{matches[0].read_text(encoding='utf-8')}")
        return "\n\n".join(parts)

    def load_trace_context(self, trace_file_path: str | Path = DEFAULT_TRACE) -> str:
        path = trace_file_path if isinstance(trace_file_path, Path) else self.root / trace_file_path
        return f"===== {path.name} =====\n{path.read_text(encoding='utf-8')}"

    def load_schema(self) -> str:
        return (self.root / SCHEMA_FILE).read_text(encoding="utf-8")

    def build_context(self, trace_file_path: str | Path | None = None) -> str:
        trace = self.load_trace_context(DEFAULT_TRACE if trace_file_path is None else trace_file_path)
        return f"{self.load_source_context()}\n\n{trace}"

    def extract(self, source_root: Path, traces: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError("JspAdapter is context-only; use agents.spec_extractor.extract_behavior_spec")
