"""LLM client router (OpenAI-compatible SDK) without exposing credentials."""

import os
from pathlib import Path

from openai import OpenAI


def _load_dotenv() -> None:
    """Load key=value pairs from parity/.env or parity-engine/.env if not already in os.environ."""
    here = Path(__file__).resolve().parent
    for env_path in (here / ".env", here.parent / ".env", here.parent.parent / ".env"):
        if env_path.is_file():
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and not os.environ.get(key):
                    os.environ[key] = value


_load_dotenv()

MODEL_API_KEY = os.getenv("MODEL_API_KEY", "") or os.getenv("META_API_KEY", "")
META_BASE_URL = os.getenv("META_BASE_URL", "https://api.meta.ai/v1")
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "muse-spark-1.3")
FIREWORKS_MODEL = os.getenv("FIREWORKS_MODEL", "muse-spark-open")
BASETEN_MODEL = os.getenv("BASETEN_MODEL", "meta-models/muse-spark-open-1026")
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY", "")
BASETEN_API_KEY = os.getenv("BASETEN_API_KEY", "")
FIREWORKS_BASE_URL = os.getenv("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")
BASETEN_BASE_URL = os.getenv("BASETEN_BASE_URL", "https://inference.baseten.co/v1")

_clients: dict[str, OpenAI] = {}


def provider_name() -> str:
    return os.getenv("PARITY_LLM_PROVIDER", "meta")


def _require_key() -> str:
    if not MODEL_API_KEY:
        raise RuntimeError("MODEL_API_KEY (or META_API_KEY) is not set; cannot create LLM clients")
    return MODEL_API_KEY


def _build(name: str) -> OpenAI:
    if name == "meta":
        return OpenAI(api_key=_require_key(), base_url=META_BASE_URL)
    if name == "fireworks":
        if FIREWORKS_API_KEY:
            return OpenAI(api_key=FIREWORKS_API_KEY, base_url=FIREWORKS_BASE_URL)
        return OpenAI(api_key=_require_key(), base_url=META_BASE_URL)
    if name == "baseten":
        if BASETEN_API_KEY:
            return OpenAI(api_key=BASETEN_API_KEY, base_url=BASETEN_BASE_URL)
        return OpenAI(api_key=_require_key(), base_url=META_BASE_URL)
    raise AttributeError(f"unknown LLM client: {name}")


def __getattr__(name: str) -> OpenAI:
    if name in ("meta_client", "fireworks_client", "baseten_client"):
        key = name.removesuffix("_client")
        if key not in _clients:
            _clients[key] = _build(key)
        return _clients[key]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
