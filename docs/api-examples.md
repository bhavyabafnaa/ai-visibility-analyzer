# API examples

The examples assume the API is available at `http://localhost:8000`. UUIDs are placeholders.
FastAPI's generated schema is available at `/openapi.json` and interactive documentation at
`/docs`.

## Health and providers

```sh
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
curl --fail http://localhost:8000/providers
```

`/health` is process liveness. `/ready` checks PostgreSQL and returns HTTP 503 when unavailable.

## Create and list projects

```sh
curl --fail-with-body \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Example Brand",
    "aliases": ["Example"],
    "site": {"url": "https://www.example.com"},
    "competitors": [
      {
        "name": "Example Competitor",
        "url": "https://competitor.example",
        "aliases": ["Competitor"]
      }
    ]
  }' \
  http://localhost:8000/projects

curl --fail http://localhost:8000/projects
curl --fail http://localhost:8000/projects/PROJECT_UUID
```

## Start and poll a crawl

Only crawl domains you are authorized to access. The crawler rejects private and otherwise
non-public destinations.

```sh
curl --fail-with-body -X POST \
  http://localhost:8000/sites/SITE_UUID/crawls

curl --fail http://localhost:8000/crawls/CRAWL_UUID
```

The create call returns HTTP 202. Poll until `status` is `succeeded` or `failed`.

## Run a deterministic sample analysis

```sh
curl --fail-with-body \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "PROJECT_UUID",
    "providers": ["mock"],
    "prompts": [
      "Compare Acme Cloud with Northstar AI for citation monitoring."
    ]
  }' \
  http://localhost:8000/analyses
```

The response contains one normalized result per provider/prompt pair. With `project_id`, it also
returns `persisted: true`.

## Add crawl evidence and explicit claim classification

```sh
curl --fail-with-body \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "PROJECT_UUID",
    "crawl_job_id": "CRAWL_UUID",
    "providers": ["openai"],
    "prompts": ["Compare Example Brand with Example Competitor."],
    "claim_classifier_provider": "openai"
  }' \
  http://localhost:8000/analyses
```

This makes provider calls, may incur cost, and sends each segmented claim plus retrieved evidence
to the selected classifier. Omit `claim_classifier_provider` to keep classification disabled.

## Retrieve persisted evidence

```sh
curl --fail http://localhost:8000/analyses/ANALYSIS_UUID/citations
curl --fail http://localhost:8000/analyses/ANALYSIS_UUID/entities
curl --fail http://localhost:8000/analyses/ANALYSIS_UUID/scores
curl --fail http://localhost:8000/analyses/ANALYSIS_UUID/claims
```

Failed and disabled provider executions are persisted but excluded from deterministic metric
denominators. Undefined scores return `value: null`, `percentage: null`, and
`is_defined: false`.

## Common error states

- `404` — project, site, crawl, or analysis does not exist.
- `422` — invalid URL/input, unknown provider, mismatched crawl/project, or duplicate/blank input.
- `503` — PostgreSQL readiness failure, provider registry unavailable, or crawl queue unavailable.
- Provider execution failures remain normalized result rows with statuses such as `timed_out`,
  `rate_limited`, `disabled`, or `error`.
