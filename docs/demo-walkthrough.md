# GeoLens 0.1.0 demo walkthrough

This walkthrough uses only local containers and deterministic fixtures. It makes no live provider
calls and does not crawl the example domains.

## 1. Start and seed

```sh
cp .env.example .env
docker compose up --build -d
docker compose ps
docker compose exec api python -m geolens_api.seed
```

Confirm that `postgres`, `redis`, `api`, `worker`, and `frontend` are healthy. If the API is not
ready, inspect `docker compose logs api`; migrations complete before its server starts.

## 2. Open the sample project

Open <http://localhost:3000>. Select **Acme Cloud** if it is not already active. The dashboard
contains four pre-filled prompts and selects **MockProvider**, which is deterministic and has no
network or credential dependency.

If the database was not seeded, the onboarding form is pre-filled with the same sample project.
Choose **Create project & continue**.

## 3. Run the evidence analysis

Choose **Run evidence analysis**. The API creates a persisted analysis run, executes the four
mock prompt fixtures, stores normalized citations and entities, calculates deterministic scores,
segments claims, and returns the completed run.

Expected high-level state:

- four eligible provider/query executions;
- Acme Cloud is visible in three fixtures;
- target and non-target citation domains are separated;
- Northstar AI and Summit Search create measurable entity gaps;
- claims are extracted but show **Not classified** because the UI did not request a classifier;
- no model-assisted claim-risk score or claim-risk recommendation is asserted.

Exact values are governed by [metrics.md](metrics.md), not by this narrative.

## 4. Inspect the evidence

Use the left navigation:

1. **Query intelligence** — provider status, target mention, citation state, and normalized domains.
2. **Citation sources** — response/domain occurrences and target-domain identification.
3. **Entity gaps** — competitor appearances where the target is absent or mentioned later.
4. **Claim risk** — segmented claims and retrieved evidence; the demo explicitly shows that no
   classifier was configured.
5. **Recommendations** — ranked actions with affected queries, provider evidence, baseline, and
   target metric.

Recommendations are deterministic presentation rules over the current run. They are not promises
of ranking improvement.

## 5. Optional API-only classifier demonstration

The dashboard intentionally does not select a live claim classifier. To test classification,
configure a live provider key, find the project UUID, and use the request in
[api-examples.md](api-examples.md) with `claim_classifier_provider`. This sends claims and retrieved
evidence to that provider and may incur cost.

## 6. Reset

Run `docker compose down` to preserve data. Run `docker compose down --volumes` only when you
intend to delete the demo database and Redis data.
