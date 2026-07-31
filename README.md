# GeoLens — AI Visibility Analyzer

[![CI](https://github.com/bhavyabafnaa/ai-visibility-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/bhavyabafnaa/ai-visibility-analyzer/actions/workflows/ci.yml)
[![Container builds](https://github.com/bhavyabafnaa/ai-visibility-analyzer/actions/workflows/container-build.yml/badge.svg)](https://github.com/bhavyabafnaa/ai-visibility-analyzer/actions/workflows/container-build.yml)

For recruiters and engineering reviewers, GeoLens is a release-candidate full-stack project that
demonstrates how an AI-facing product can remain auditable: provider responses are normalized and
preserved, measurements are deterministic, recommendations link back to evidence, and website
crawling is bounded by explicit security controls.

GeoLens runs a provider/query matrix to measure brand visibility, citation coverage, source share,
and competitive entity coverage. The monorepo combines a FastAPI API, a Next.js dashboard,
PostgreSQL persistence, a Redis-backed Celery worker, and a bounded website crawler behind a
provider-neutral contract.

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
demo prompts. The `.example` domains are deliberately non-routable examples, so the dashboard
disables crawling for the seeded project. MockProvider analysis remains available without crawl
evidence. Follow the [demo walkthrough](docs/demo-walkthrough.md) for the expected screens and
evidence states.

## Dashboard

The dashboard supports project creation and switching, provider and query selection, persisted
analysis evidence, deterministic metrics, claim review, and ranked recommendations. Its Website
evidence panel can explicitly queue a bounded crawl and poll its status. A succeeded crawl is
optional evidence: the dashboard attaches its `crawl_job_id` to the next analysis, while analysis
without a crawl continues to work.

![GeoLens overview showing deterministic metrics and evidence tables](docs/screenshots/overview.png)

The four-query Acme MockProvider demo produces these reproducible metrics:

- **Visibility rate:** 75% (3/4)
- **Target citation coverage:** 67% (2/3)
- **Citation share:** 25% (2/8)
- **Rank-weighted share of AI voice:** 31%
- **Entity coverage:** 67% (8/12)

The [query intelligence view](docs/screenshots/query-intelligence.png) exposes every provider/query
outcome, target mention, citation state, and normalized domain. The
[recommendations view](docs/screenshots/recommendations.png) turns those measured gaps into ranked
actions with affected queries, provider evidence, current values, and target values.

## End-to-End Workflow

1. **Define the comparison set.** Create a target brand, domain, aliases, and competitors in
   [Project setup](docs/screenshots/project-setup.png). The seeded Acme Cloud project already
   contains the deterministic demo configuration.
2. **Choose the execution matrix.** Review the prompts, select enabled providers, and start the
   analysis. MockProvider needs no API key or external provider call.
3. **Persist and normalize evidence.** GeoLens stores the raw provider response for auditability,
   normalizes citations and entity mentions, and calculates the documented metrics.
4. **Inspect gaps and actions.** Move from the overview into query-level evidence, citation sources,
   entity gaps, claim review, and evidence-linked recommendations.
5. **Optionally attach website evidence.** For a public site you are authorized to crawl, create a
   separate project and choose **Crawl website**. The crawl moves through
   [queued](docs/screenshots/crawl-queued.png) and running states before the dashboard shows the
   [succeeded page and error counts](docs/screenshots/crawl-succeeded.png). The next analysis for
   that same project attaches the succeeded crawl and confirms the
   [evidence page count](docs/screenshots/evidence-attached.png).

The crawl screenshots use a separate authorized-site project; they do not represent the Acme demo
metrics or a live-provider result. The seeded `acme.example` project cannot be crawled and remains
the deterministic, no-network MockProvider demonstration. See the
[screenshot evidence index](docs/screenshots/README.md) and the full
[demo walkthrough](docs/demo-walkthrough.md).

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

Model identifiers are environment-configured and must be set to models enabled for the developer's
provider account. Provider model availability may change.

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
