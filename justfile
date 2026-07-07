set dotenv-load := true

backend := "mnemosyne-backend"
web := "mnemosyne-web"

default:
    @just --list

install:
    cd {{backend}} && uv sync
    -cd {{web}} && npm install

dev:
    cd {{backend}} && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

mcp:
    cd {{backend}} && uv run python -m app.interfaces.mcp.server

worker:
    cd {{backend}} && uv run arq app.infrastructure.queue.worker.WorkerSettings

test:
    cd {{backend}} && uv run pytest tests/unit tests/integration

test-unit:
    cd {{backend}} && uv run pytest tests/unit

test-integration:
    cd {{backend}} && uv run pytest tests/integration -m integration

test-bdd-local server_url="http://localhost:8000":
    cd {{backend}} && uv run pytest tests/bdd -m bdd --server-url={{server_url}}

test-bdd-staging:
    cd {{backend}} && uv run pytest tests/bdd -m bdd --server-url=$STAGING_SERVER_URL

coverage:
    cd {{backend}} && uv run pytest tests/unit --cov --cov-report=term-missing

lint:
    cd {{backend}} && uv run ruff check .

format:
    cd {{backend}} && uv run ruff format .

typecheck:
    cd {{backend}} && uv run mypy app

quality: lint typecheck coverage

docker-up:
    docker compose up -d

docker-down:
    docker compose down

docker-logs service="":
    docker compose logs -f {{service}}

migrate:
    cd {{backend}} && uv run alembic upgrade head

revision name:
    cd {{backend}} && uv run alembic revision --autogenerate -m "{{name}}"

openspec-validate:
    openspec validate --all --strict
