from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class SourceAdapter(ABC):
    @abstractmethod
    def extract(self, source_root: Path, traces: list[dict[str, Any]]) -> dict[str, Any]:
        """Return a contract-shaped BehaviorSpec or raise a parsing error."""
        raise NotImplementedError

