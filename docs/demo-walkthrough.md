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

Expected deterministic metrics:

- **Visibility rate:** 75% (3/4)
- **Target citation coverage:** 67% (2/3)
- **Citation share:** 25% (2/8)
- **Rank-weighted share of AI voice:** 31%
- **Entity coverage:** 67% (8/12)

The formulas and denominator rules are documented in [metrics.md](metrics.md).

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

## 6. Real public website crawl

Use this separate workflow only for a public website that you are authorized to crawl. Do not use
the seeded project: its `.example` hostname is intentionally non-routable and its crawl action is
disabled.

1. Open **Project setup** and create a project with the real public website URL.
2. Return to **Overview** and choose **Crawl website** in the Website evidence panel.
3. Confirm **Crawl queued**. The API has persisted the job and submitted it to Celery; the worker
   has not necessarily started fetching pages yet.
4. Wait while the dashboard polls through queued and running states until the crawl succeeds or
   fails.
5. Inspect the terminal counts. **Pages crawled** is the number of extracted pages persisted for
   evidence, while **Errors** is the number of recorded per-URL failures. A succeeded bounded crawl
   can still report non-zero URL errors.
6. After **Website crawl succeeded** appears, choose **Run analysis**. The dashboard automatically
   includes that crawl's `crawl_job_id` and the completion banner reports **Website evidence
   attached** with the page count.

Only a succeeded crawl is eligible for attachment; queued, running, and failed crawls are not.
Crawling remains optional, and the crawler's safety and size limits mean it samples bounded website
content rather than exhaustively indexing a large site.

### Project isolation

Crawl and analysis state follows the active project. Switching projects clears the displayed run
and crawl state, loads the selected site's latest crawl status, and ignores late status or analysis
responses from the previously selected project. Before attachment, the UI verifies that the crawl
belongs to the active site's ID; the API also rejects a crawl whose site belongs to a different
project. Evidence from one project therefore cannot be attached to another project's analysis.

The [queued](screenshots/crawl-queued.png), [succeeded](screenshots/crawl-succeeded.png), and
[evidence-attached](screenshots/evidence-attached.png) screenshots document these states for a
separate authorized-site project. They are not live-provider results and do not replace the Acme
MockProvider metrics above.

## 7. Reset

Run `docker compose down` to preserve data. Run `docker compose down --volumes` only when you
intend to delete the demo database and Redis data.
