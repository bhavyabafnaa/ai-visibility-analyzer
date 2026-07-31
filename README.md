# GeoLens

GeoLens is a release-candidate AI visibility and citation intelligence application. It runs a
provider/query matrix, normalizes answer evidence, calculates deterministic visibility metrics,
and produces evidence-linked review recommendations. The monorepo contains a FastAPI API, a
Next.js dashboard, PostgreSQL persistence, a Redis-backed Celery worker, and a bounded website
crawler.

Version: **0.1.0**

> GeoLens 0.1.0 has no authentication, authorization, tenant isolation, or rate limiting. Run it
> on a trusted machine or behind an authenticated reverse proxy; do not expose the Compose stack
> directly to the public internet.

## Repository map

```text
backend/                  FastAPI API, worker, migrations, seed, and tests
frontend/                 Next.js dashboard and tests
.github/workflows/        CI and container-build validation
docs/                     Architecture, operations, API, and release documentation
compose.yaml              Five-service local release topology
Makefile                  Common development and validation commands
```

Start with:

- [Architecture](docs/architecture.md)
- [Demo walkthrough](docs/demo-walkthrough.md)
- [API examples](docs/api-examples.md)
- [Metric formulas](docs/metrics.md)
- [Security notes](docs/security.md)
- [Limitations](docs/limitations.md)
- [Provider/API disclaimer](docs/provider-disclaimer.md)
- [0.1.0 release notes](docs/releases/0.1.0.md)

## Quick start

Prerequisites are Docker Desktop (or Docker Engine) with Docker Compose v2.

```sh
cp .env.example .env
docker compose up --build -d
docker compose ps
```

PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

The API container applies `alembic upgrade head` before Uvicorn starts. PostgreSQL and Redis
health gate the API; API readiness gates the worker and frontend. Seed the idempotent sample
project after the stack is healthy:

```sh
docker compose exec api python -m geolens_api.seed
```

Open:

- Dashboard: <http://localhost:3000>
- API: <http://localhost:8000>
- OpenAPI: <http://localhost:8000/docs>
- Process health: <http://localhost:8000/health>
- Database readiness: <http://localhost:8000/ready>

All published ports bind to `127.0.0.1` by default. Set `BIND_ADDRESS` only when the surrounding
network and access controls are intentional.

Stop the stack while keeping its volumes:

```sh
docker compose down
```

Remove the local PostgreSQL and Redis data only when that deletion is intended:

```sh
docker compose down --volumes
```

## Demo data

`geolens_api.seed` creates one sample project:

- target: Acme Cloud (`acme.example`)
- competitors: Northstar AI and Summit Search
- aliases matching the pre-filled dashboard prompt set

The backend-only `MockProvider` supplies deterministic sample answers and citations for the four
demo prompts. The `.example` domains are deliberately non-routable examples; do not start a crawl
for the seeded project. Follow the [demo walkthrough](docs/demo-walkthrough.md) for the expected
screens and evidence states.

## Screenshots

> **Screenshot placeholder — Project setup:** capture the pre-filled Acme Cloud onboarding screen
> at desktop width before the 0.1.0 announcement.

> **Screenshot placeholder — Evidence overview:** capture the completed MockProvider run with the
> five deterministic metric cards and provider/query table.

> **Screenshot placeholder — Recommendations:** capture the ranked recommendation cards with
> affected queries, provider evidence, and expected metric fields visible.

The capture sizes, redaction rules, and target filenames are in
[docs/screenshots/README.md](docs/screenshots/README.md).

## Provider execution

`GET /providers` reports whether each adapter is enabled. `mock` is always enabled. OpenAI,
Gemini, and Perplexity remain disabled until their corresponding server-side key is present.
Disabled providers never fall back to a different provider.

```json
{
  "project_id": "PROJECT_UUID",
  "providers": ["mock"],
  "prompts": ["Compare Acme Cloud with Northstar AI for citation monitoring."]
}
```

Persisted artifacts are available at:

- `GET /analyses/{analysis_id}/citations`
- `GET /analyses/{analysis_id}/entities`
- `GET /analyses/{analysis_id}/scores`
- `GET /analyses/{analysis_id}/claims`

Claim classification is opt-in through `claim_classifier_provider`. Without it, claims are
segmented and linked to stored evidence but are explicitly marked `not_configured`; GeoLens does
not calculate a model-assisted risk score. A calculated claim-support risk is a prioritization
estimate, never objective truth.

Provider endpoints, model availability, billing, data handling, and response schemas are owned
by their respective vendors and may change independently. Read the
[provider/API disclaimer](docs/provider-disclaimer.md) before enabling live calls.

## Local development

Python 3.10+ and Node.js 22 are supported by the checked-in tooling.

```sh
python -m venv backend/.venv
backend/.venv/bin/python -m pip install -e "backend[dev]"
npm --prefix frontend ci
docker compose up -d postgres redis
```

On Windows, use `backend\.venv\Scripts\python.exe` in place of
`backend/.venv/bin/python`. When running the backend on the host, use localhost database and Redis
URLs rather than the Compose-only hostnames:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://geolens:geolens_dev_password@127.0.0.1:5432/geolens"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
backend\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
backend\.venv\Scripts\python.exe -m uvicorn geolens_api.main:app --app-dir backend/src --reload
```

In another terminal:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://geolens:geolens_dev_password@127.0.0.1:5432/geolens"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
backend\.venv\Scripts\celery.exe -A geolens_api.celery_app:celery_app worker --loglevel=INFO
```

Start the frontend with:

```sh
npm --prefix frontend run dev
```

The browser calls the same-origin `/api/geolens` proxy. `GEOLENS_API_URL` is read by the Next.js
server only; provider credentials are never bundled into browser code.

## Validation

With GNU Make:

```sh
make lint
make typecheck
make test
make build
docker compose config --quiet
```

Equivalent direct commands:

```sh
backend/.venv/bin/python -m ruff check backend
backend/.venv/bin/python -m ruff format --check backend
backend/.venv/bin/python -m mypy backend
backend/.venv/bin/python -m pytest backend -m "not integration and not live"
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
docker compose config --quiet
docker build -t geolens-api:local backend
docker build -t geolens-frontend:local frontend
```

PostgreSQL integration tests require a disposable database:

```sh
TEST_DATABASE_URL=postgresql+asyncpg://geolens:geolens_dev_password@127.0.0.1:5432/geolens_test \
  backend/.venv/bin/python -m pytest backend/tests/integration
```

The CI workflow provisions that database as a PostgreSQL service container and runs the
integration suite. Live provider tests remain opt-in and are excluded from CI because they incur
third-party traffic and may incur cost.
