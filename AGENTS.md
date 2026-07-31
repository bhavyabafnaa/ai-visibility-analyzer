# AGENTS.md

## Product goal

GeoLens is an AI visibility and citation intelligence platform. It crawls
company websites, evaluates web-grounded AI responses, normalizes citations,
measures competitive visibility and generates evidence-linked GEO actions.

## Architecture

- Backend: FastAPI, SQLAlchemy and PostgreSQL.
- Background jobs: Celery and Redis.
- Frontend: Next.js and TypeScript.
- Infrastructure: Docker Compose.
- Database migrations: Alembic.
- Provider integrations must implement the shared provider contract.
- Provider response formats must not leak into scoring modules.

## Engineering rules

- Never commit API keys or credentials.
- Do not call provider APIs from frontend code.
- Keep API routes thin.
- Put business logic in services.
- Every database change requires an Alembic migration.
- Every feature and bug fix requires tests.
- Mock external APIs in CI.
- Preserve raw provider responses for auditability.
- Do not silently fall back between providers.
- Do not describe claim-risk analysis as objective truth.
- Validate crawl targets against SSRF and private-network access.
- Use bounded timeouts, retries, concurrency and page limits.

## Definition of done

Before reporting completion:

1. Run Ruff.
2. Run Ruff formatting checks.
3. Run MyPy.
4. Run backend tests.
5. Run frontend linting.
6. Run frontend type checking.
7. Run frontend tests.
8. Run the frontend production build.
9. Validate Docker Compose.
10. Report limitations and unfinished work.
11. Do not create a commit unless explicitly requested.