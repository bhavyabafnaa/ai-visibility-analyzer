# API examples

These examples assume the API is available at `http://localhost:8000`.

UUID values are placeholders. FastAPI's generated OpenAPI schema is available at
`/openapi.json`, and interactive documentation is available at `/docs`.

## Health and providers

```sh
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
curl --fail http://localhost:8000/providers
```

`/health` reports process liveness.

`/ready` checks PostgreSQL connectivity and returns HTTP 503 while the database
is unavailable.

`/providers` reports which provider adapters are enabled and which model
identifier is configured for each provider.

## Create and list projects

```sh
curl --fail-with-body \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Example Brand",
    "aliases": ["Example"],
    "site": {
      "url": "https://www.example.com"
    },
    "competitors": [
      {
        "name": "Example Competitor",
        "url": "https://competitor.example",
        "aliases": ["Competitor"]
      }
    ]
  }' \
  http://localhost:8000/projects
```

List projects:

```sh
curl --fail http://localhost:8000/projects
```

Retrieve one project:

```sh
curl --fail http://localhost:8000/projects/PROJECT_UUID
```

## Start and poll a crawl

Only crawl public websites that you are authorized to access.

The crawler rejects private, local, metadata-service, link-local, and otherwise
non-public destinations.

Start a crawl:

```sh
curl --fail-with-body -X POST \
  http://localhost:8000/sites/SITE_UUID/crawls
```

The API returns HTTP 202 with a crawl object similar to:

```json
{
  "id": "CRAWL_UUID",
  "site_id": "SITE_UUID",
  "status": "pending",
  "started_at": null,
  "completed_at": null,
  "error_message": null,
  "celery_task_id": "CELERY_TASK_ID",
  "page_count": 0,
  "error_count": 0,
  "created_at": "2026-07-31T12:00:00Z",
  "updated_at": "2026-07-31T12:00:00Z"
}
```

Poll the crawl:

```sh
curl --fail http://localhost:8000/crawls/CRAWL_UUID
```

Continue polling while `status` is:

```text
pending
running
```

Stop when it becomes:

```text
succeeded
failed
```

Only a succeeded crawl can be attached as evidence to an analysis.

## Queue a deterministic MockProvider analysis

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

The API returns HTTP 202. It does not wait for provider execution to finish.

Example initial response:

```json
{
  "analysis_id": "ANALYSIS_UUID",
  "project_id": "PROJECT_UUID",
  "crawl_job_id": null,
  "status": "pending",
  "started_at": null,
  "completed_at": null,
  "error_message": null,
  "celery_task_id": "CELERY_TASK_ID",
  "provider_configurations": [
    {
      "name": "mock",
      "model_identifier": "mock-v1"
    }
  ],
  "prompts": [
    "Compare Acme Cloud with Northstar AI for citation monitoring."
  ],
  "claim_classifier_configuration": null,
  "results": [],
  "persisted": true,
  "created_at": "2026-07-31T12:00:00Z",
  "updated_at": "2026-07-31T12:00:00Z"
}
```

Poll the analysis:

```sh
curl --fail http://localhost:8000/analyses/ANALYSIS_UUID
```

Continue polling while `status` is:

```text
pending
running
```

Stop when it becomes:

```text
succeeded
completed_with_errors
failed
```

A successful or partially successful terminal response contains one normalized
result per provider/prompt execution.

## Queue an analysis with crawl evidence

```sh
curl --fail-with-body \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "PROJECT_UUID",
    "crawl_job_id": "CRAWL_UUID",
    "providers": ["mock"],
    "prompts": [
      "Compare Example Brand with Example Competitor."
    ]
  }' \
  http://localhost:8000/analyses
```

The crawl must:

- exist;
- belong to the selected project;
- have completed successfully.

The selected crawl's extracted page text becomes part of the claim-evidence
retrieval set.

Provider citations remain separate evidence records and are not represented as
having originated from the crawled website.

## Queue a live-provider analysis

Configure the provider key and an explicit model identifier in `.env` before
starting the API and worker.

Example:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=ACCOUNT_ENABLED_MODEL_IDENTIFIER
```

Then submit:

```sh
curl --fail-with-body \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "PROJECT_UUID",
    "providers": ["openai"],
    "prompts": [
      "Compare Example Brand with Example Competitor."
    ]
  }' \
  http://localhost:8000/analyses
```

This request may create third-party traffic and incur provider charges.

GeoLens persists the exact provider and model identifier when the job is queued.
The worker rejects configuration drift rather than silently using another model.

## Add explicit claim classification

```sh
curl --fail-with-body \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "PROJECT_UUID",
    "crawl_job_id": "CRAWL_UUID",
    "providers": ["openai"],
    "prompts": [
      "Compare Example Brand with Example Competitor."
    ],
    "claim_classifier_provider": "openai"
  }' \
  http://localhost:8000/analyses
```

This configuration:

- calls the selected answer provider;
- segments factual claims;
- retrieves relevant stored crawl and citation evidence;
- sends each claim and its retrieved evidence to the explicit classifier;
- may incur additional provider cost.

Omit `claim_classifier_provider` to keep classification disabled.

Without a classifier, claims are stored with `classifier = not_configured`, and
GeoLens does not calculate a model-assisted aggregate claim-risk score.

## Retrieve persisted evidence

After the analysis reaches a terminal state, retrieve normalized citations:

```sh
curl --fail \
  http://localhost:8000/analyses/ANALYSIS_UUID/citations
```

Retrieve extracted entities:

```sh
curl --fail \
  http://localhost:8000/analyses/ANALYSIS_UUID/entities
```

Retrieve deterministic scores:

```sh
curl --fail \
  http://localhost:8000/analyses/ANALYSIS_UUID/scores
```

Retrieve claims and linked evidence:

```sh
curl --fail \
  http://localhost:8000/analyses/ANALYSIS_UUID/claims
```

Failed, disabled, timed-out, and rate-limited provider executions are persisted
as normalized result rows but excluded from deterministic metric denominators.

Undefined scores return:

```json
{
  "value": null,
  "percentage": null,
  "is_defined": false
}
```

## Common error states

- `404` — project, site, crawl, or analysis does not exist.
- `422` — invalid input, unknown provider, mismatched crawl/project, duplicate
  prompts, duplicate providers, missing model configuration, or unsafe URL.
- `503` — PostgreSQL readiness failure, provider registry unavailable, Redis
  unavailable, crawl queue unavailable, or analysis queue unavailable.

Provider execution failures do not necessarily make the API request fail.
They are preserved as normalized execution results with statuses such as:

```text
timed_out
rate_limited
disabled
error
```

An analysis containing both successful and unsuccessful executions can finish
with:

```text
completed_with_errors
```
