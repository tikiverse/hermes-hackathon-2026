# Image for the one-line demo (scripts/demo.sh): Hermes plus this repo's plugins, run next to an Ollama container.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /usr/local/bin/uv

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY plugins ./plugins
COPY scripts ./scripts
COPY demo ./demo

ENV PATH="/app/.venv/bin:$PATH" HERMES_HOME=/data/hermes
VOLUME /data/hermes
ENTRYPOINT ["/app/demo/entrypoint.sh"]
