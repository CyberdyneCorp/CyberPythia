FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm

RUN groupadd -r mnemosyne && useradd -r -g mnemosyne mnemosyne
WORKDIR /app
COPY --from=builder --chown=mnemosyne:mnemosyne /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1

USER mnemosyne
EXPOSE 8000 8100
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
