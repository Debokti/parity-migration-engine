# Parity inference + verification CLI (Python 3.13).
# No credentials baked in: keys arrive via environment (.env / compose env_file).
# Default command prints help; run one-shot ops with e.g.
#   docker run --rm --env-file .env parity-llm ask "..."
# NOTE: entrypoint calls parity_cli.py directly because the pyproject
# [project.scripts] entry (parity_cli:app) has no matching `app` object.
FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /parity
COPY parity-engine/pyproject.toml parity-engine/
COPY parity-engine/parity_cli.py parity-engine/config.py parity-engine/
COPY parity-engine/agents parity-engine/adapters parity-engine/verifier parity-engine/modal_sandbox parity-engine/
RUN apt-get update \
    && pip install ./parity-engine \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*
COPY contracts ./contracts
COPY artifacts/specs ./artifacts/specs
COPY artifacts/golden-traces ./artifacts/golden-traces
RUN mkdir -p artifacts/replays artifacts/reports runs
ENTRYPOINT ["python", "parity-engine/parity_cli.py"]
CMD ["ask", "--help"]
