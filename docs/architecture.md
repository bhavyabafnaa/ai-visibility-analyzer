# GeoLens architecture

## Status and scope

This document describes the project foundation. The repository does not yet contain provider
integrations, prompt execution, citation extraction, metric computation, authentication, or
other business workflows.

## System context

```mermaid
flowchart LR
    User[User] --> Web[Next.js frontend]
    Web --> API[FastAPI backend]
    API -. future persistence .-> DB[(PostgreSQL)]
    API -. future cache and jobs .-> Cache[(Redis)]
```

The dashed connections represent infrastructure boundaries that are configured locally but
are not used by application code yet.

## Components

### Frontend

The Next.js TypeScript application owns browser-facing presentation and, in future, will call
the backend over HTTP. The initial application is a static placeholder with no business
behavior. `NEXT_PUBLIC_API_URL` is the public backend base URL.

### Backend

The FastAPI application owns the HTTP API boundary. It currently exposes only:

- `GET /health` for process health
- FastAPI's generated OpenAPI schema and documentation

The package uses a `src` layout so imports resolve from the installed application rather than
the repository working directory. Domain modules and routers should be introduced only when a
concrete use case needs them.

### PostgreSQL

PostgreSQL is reserved for durable relational data. No schema, migration tool, or database
client is selected yet because there is no persistence requirement to model.

### Redis

Redis is reserved for ephemeral caching, rate coordination, and/or background job
infrastructure. No queue library or key design is selected yet.

## Runtime topology

Docker Compose supplies one container for each component and health checks for PostgreSQL,
Redis, and the backend. The frontend waits for the backend's process health; the backend waits
for its future infrastructure dependencies to accept connections.

The `/health` response means only that the API process can serve HTTP. It intentionally does
not report PostgreSQL or Redis readiness until application code actually depends on them.

## Configuration

Configuration is passed through environment variables. `.env.example` contains local,
non-sensitive defaults and may be copied to `.env`. Real secrets must never be committed.
Provider-specific keys are outside the current scope.

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

## Deferred decisions

The following choices require business requirements and are intentionally open:

- authentication, authorization, and tenant isolation
- database schema and migration tooling
- background task and scheduling framework
- AI/search provider contracts
- observability and deployment platform
- API versioning and generated client strategy
- metric materialization and aggregation windows
