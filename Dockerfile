# syntax=docker/dockerfile:1.7

FROM python:3.13.15-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

FROM python:3.13.15-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/orysys \
    NLTK_DATA=/usr/local/share/nltk_data
WORKDIR /app

RUN groupadd --gid 10001 orysys \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin orysys

COPY --from=builder --chown=orysys:orysys /app/.venv /app/.venv
RUN mkdir -p /usr/local/share/nltk_data \
    && /app/.venv/bin/python -m nltk.downloader -d /usr/local/share/nltk_data punkt_tab punkt stopwords \
    && chmod -R a+r /usr/local/share/nltk_data
COPY --chown=orysys:orysys alembic.ini ./
COPY --chown=orysys:orysys migrations ./migrations
COPY --chown=orysys:orysys src ./src
COPY --chown=orysys:orysys data ./data

USER 10001:10001
EXPOSE 8000 8001 8501

CMD ["uvicorn", "orysys.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
