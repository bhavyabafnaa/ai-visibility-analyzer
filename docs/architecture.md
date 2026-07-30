# GeoLens architecture

## Status and scope

This document describes the project foundation, project persistence, secure crawl pipeline,
and provider-neutral prompt execution. Metric computation and authentication are not yet
implemented.

## System context

```mermaid
flowchart LR
    User[User] --> Web[Next.js frontend]
    Web --> API[FastAPI backend]
    API --> DB[(PostgreSQL)]
    API --> Queue[(Redis)]
    API --> Providers[AI and search providers]
    Queue --> Worker[Celery worker]
    Worker --> DB
    Worker --> Site[Configured website]
```

## Components

### Frontend

The Next.js TypeScript application owns browser-facing presentation and, in future, will call
the backend over HTTP. The initial application is a static placeholder with no business
behavior. `NEXT_PUBLIC_API_URL` is the public backend base URL.

### Backend

The FastAPI application owns the HTTP API boundary. It exposes:

- `GET /health` for process health
- `GET /ready` for PostgreSQL readiness
- `POST /projects` to create a project aggregate
- `GET /projects/{project_id}` to retrieve a project
- `GET /projects` to list projects
- `POST /sites/{site_id}/crawls` to validate a site and queue a crawl
- `GET /crawls/{crawl_id}` to read crawl status and result counts
- `GET /providers` to report enabled and disabled backend providers
- `POST /analyses` to execute selected providers against selected prompts
- FastAPI's generated OpenAPI schema and documentation

Routes validate and serialize HTTP data, services coordinate use cases and transactions, and
repositories own SQLAlchemy queries. The package uses a `src` layout so imports resolve from
the installed application rather than the repository working directory.

### Provider adapters

Provider clients are created during the backend application lifespan and never exposed to the
frontend. A neutral contract carries provider and model identifiers, response text, normalized
citations, raw JSON, token usage, latency, status, and structured errors. Analysis orchestration
depends only on that contract.

`MockProvider` supplies deterministic recorded and synthetic results. OpenAI uses the Responses
API with hosted web search, Gemini uses the Interactions API with Google Search, and Perplexity
uses Sonar. Each adapter owns its request and citation parsing at the infrastructure edge. Shared
HTTP behavior enforces timeouts, bounded retries, exponential backoff, `Retry-After` handling,
and explicit terminal rate-limit errors.

Missing credentials install a disabled placeholder under that provider's own name. Selecting it
returns a disabled result; the registry never routes the request to another provider. The
analysis endpoint runs the provider/prompt matrix concurrently and returns results in stable
provider-then-prompt order.

### PostgreSQL

PostgreSQL stores projects, their primary sites and competitors, crawl-job and analysis-run
lifecycle records, extracted crawl pages, and per-URL crawl errors. SQLAlchemy provides
asynchronous sessions through `asyncpg`; Alembic owns schema migrations. Primary keys are
UUIDs and all timestamps are timezone-aware.

### Crawler and worker

Redis is the Celery broker and result backend. The API commits a pending crawl job before
enqueuing its UUID. A worker marks it running, crawls with HTTPX, persists extracted pages and
errors, and records terminal counts and status.

The crawler resolves and pins public IP addresses before connecting, revalidates redirects,
stays on the exact configured hostname, parses robots and sitemaps, and streams bounded
responses. Sitemap URLs have deterministic priority over link-discovered URLs. Page work is
processed in stable batches so concurrency cannot change the selected page set. Canonical
identities and normalized URLs are deduplicated.

HTML extraction stores canonical URL, title, description, headings, main text, JSON-LD,
internal links, and a SHA-256 hash of the fetched content. JavaScript rendering is optional
behind an interface whose implementations must enforce the same hostname, address, timeout,
and size policies; Playwright is not installed by default.

## Runtime topology

Docker Compose supplies one container for each component and health checks for PostgreSQL,
Redis, and the backend. The API and worker wait for PostgreSQL and Redis; the frontend waits
for the backend's process health.

The `/health` response means only that the API process can serve HTTP. `/ready` executes a
database query and returns HTTP 503 while PostgreSQL is unavailable. A Redis failure during
crawl creation is surfaced as HTTP 503 and persisted on the crawl job.

## Configuration

Configuration is passed through environment variables. `.env.example` contains local,
non-sensitive defaults and may be copied to `.env`. Real secrets must never be committed.
Provider model names, API keys, request timeouts, retry limits, and backoff caps are configured
through environment variables. Empty provider keys disable their provider. Secrets have no
checked-in values.

## Dependency direction

Future code should preserve these boundaries:

```text
HTTP/UI adapters -> application use cases -> domain definitions
                                |
                                v
                     infrastructure adapters
```

Framework and provider objects should remain at the edges. Domain metric definitions should
not depend on FastAPI, Next.js, a model provider, PostgreSQL, or Redis.

## Crawl configuration

Crawler limits use `GEOLENS_CRAWLER_*` environment variables. The checked-in example covers
page count, depth, decoded response bytes, total request timeout, in-crawl concurrency,
redirect count, sitemap count, renderer fallback threshold, and user agent.

## Deferred decisions

The following choices require business requirements and are intentionally open:

- authentication, authorization, and tenant isolation
- observability and deployment platform
- API versioning and generated client strategy
- metric materialization and aggregation windows
