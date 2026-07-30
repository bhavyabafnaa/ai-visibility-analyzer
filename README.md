# GeoLens

GeoLens is an AI visibility and citation intelligence platform. The repository contains a
FastAPI service, a Next.js application, PostgreSQL persistence, a Redis-backed Celery worker,
and a bounded website crawler. Backend-only adapters support deterministic mock, OpenAI,
Gemini, and Perplexity prompt execution through one provider-neutral response contract.

## Repository layout

```text
backend/        FastAPI application and Python tests
frontend/       Next.js TypeScript application
docs/           Architecture and metric definitions
compose.yaml    Local full-stack environment
Makefile        Common development commands
```

See [docs/architecture.md](docs/architecture.md) for component boundaries and
[docs/metrics.md](docs/metrics.md) for proposed metric definitions.

## Prerequisites

- Docker Desktop with Docker Compose v2
- Python 3.10 or newer for local backend development
- Node.js 20.9 or newer and npm for local frontend development
- GNU Make is optional

## Start the full stack with Docker

Create the local environment file:

```powershell
Copy-Item .env.example .env
```

On macOS or Linux:

```sh
cp .env.example .env
```

Build and start all five services:

```sh
docker compose up --build
```

Apply database migrations:

```sh
make migrate
```

Seed the idempotent Acme Cloud demo project:

```sh
make seed
```

The dashboard is also pre-filled with this configuration when the database is empty. Its default
prompt set has deterministic `MockProvider` fixtures with measurable citation, entity, and claim
evidence gaps, so the local recommendation workflow requires no provider credential.

The services are then available at:

- Frontend: <http://localhost:3000>
- Backend API: <http://localhost:8000>
- Backend health: <http://localhost:8000/health>
- Backend readiness: <http://localhost:8000/ready>
- Configured provider status: <http://localhost:8000/providers>
- OpenAPI documentation: <http://localhost:8000/docs>
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

Create a crawl with `POST /sites/{site_id}/crawls`; poll
`GET /crawls/{crawl_id}` for status and persisted page/error counts.

Start a provider analysis with `POST /analyses`:

```json
{
  "providers": ["mock", "openai"],
  "prompts": ["What sources describe Acme's product category?"]
}
```

The endpoint returns one normalized result for every selected provider and prompt. A live
provider without its corresponding `OPENAI_API_KEY`, `GEMINI_API_KEY`, or
`PERPLEXITY_API_KEY` is reported as disabled and is never replaced by another provider.
Provider model identifiers and request resilience limits are configured in `.env.example`.

To persist deterministic metrics and claim-support analysis, include a project. A crawl and
model classifier are explicit:

```json
{
  "project_id": "00000000-0000-0000-0000-000000000000",
  "crawl_job_id": "00000000-0000-0000-0000-000000000000",
  "providers": ["openai"],
  "prompts": ["Compare Acme with its alternatives."],
  "claim_classifier_provider": "openai"
}
```

Persisted results are available from:

- `GET /analyses/{analysis_id}/citations`
- `GET /analyses/{analysis_id}/entities`
- `GET /analyses/{analysis_id}/scores`
- `GET /analyses/{analysis_id}/claims`

The claim-support risk score is a disclosed model-assisted estimate, not objective truth. Exact
normalization, metric, evidence, and risk formulas are documented in
[docs/metrics.md](docs/metrics.md).

Stop the stack without removing persistent data:

```sh
docker compose down
```

## Start services locally

Start only the infrastructure:

```sh
docker compose up -d postgres redis
```

### Backend

PowerShell:

```powershell
py -3.10 -m venv backend/.venv
backend\.venv\Scripts\python -m pip install -e "backend[dev]"
backend\.venv\Scripts\python -m uvicorn geolens_api.main:app --app-dir backend/src --reload
backend\.venv\Scripts\celery -A geolens_api.celery_app:celery_app worker --loglevel=INFO
```

macOS or Linux:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e "backend[dev]"
backend/.venv/bin/python -m uvicorn geolens_api.main:app --app-dir backend/src --reload
backend/.venv/bin/celery -A geolens_api.celery_app:celery_app worker --loglevel=INFO
```

### Frontend

```sh
npm --prefix frontend ci
npm --prefix frontend run dev
```

The browser uses a same-origin `/api/geolens` route. The Next.js server reads the server-only
`GEOLENS_API_URL` variable and defaults to `http://localhost:8000` for local development. Provider
credentials are never included in frontend environment variables or sent to the browser.

## Development commands

If GNU Make is available:

```sh
make setup
make migrate
make seed
make lint
make typecheck
make test
make build
make check
make infra
make up
make down
```

The equivalent direct checks are:

PowerShell:

```powershell
backend\.venv\Scripts\python -m ruff check backend
backend\.venv\Scripts\python -m ruff format --check backend
backend\.venv\Scripts\python -m mypy backend
backend\.venv\Scripts\python -m alembic -c backend/alembic.ini upgrade head
backend\.venv\Scripts\python -m pytest backend
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run build
docker compose config --quiet
```

macOS or Linux:

```sh
backend/.venv/bin/python -m ruff check backend
backend/.venv/bin/python -m ruff format --check backend
backend/.venv/bin/python -m mypy backend
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/python -m pytest backend
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run build
docker compose config --quiet
```

The frontend test command currently succeeds with no tests. Test coverage should be added
alongside the first frontend behavior.

PostgreSQL integration tests require `TEST_DATABASE_URL` to identify a dedicated disposable
database. The suite applies the Alembic migration before testing and downgrades it afterward:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://geolens:geolens_dev_password@localhost:5432/geolens_test"
backend\.venv\Scripts\python -m pytest backend\tests\integration
```

Live provider contract tests are opt-in, never run in CI, and require both credentials and an
explicit local flag:

```powershell
$env:GEOLENS_RUN_LIVE_PROVIDER_TESTS = "1"
backend\.venv\Scripts\python -m pytest backend\tests\live
```
