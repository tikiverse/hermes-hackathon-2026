FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /usr/local/bin/uv

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY plugins ./plugins
COPY docker ./docker

ENV PATH="/app/.venv/bin:$PATH" \
    HERMES_HOME=/data/hermes \
    QUICK_EVAL_LOCAL_HOST=host.docker.internal

VOLUME /data/hermes
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["hermes"]
