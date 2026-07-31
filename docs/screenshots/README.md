# Screenshot evidence index

These images document the GeoLens 0.1 dashboard with MockProvider selected. The Acme Cloud images
show the deterministic seeded demo. The crawl images show a separate authorized public-site
project and do not claim a live-provider result.

- [`project-setup.png`](project-setup.png) — proves that a project can define its target brand,
  primary public URL, aliases, and competitor comparison set.
- [`overview.png`](overview.png) — proves that the seeded Acme run presents the five deterministic
  metric cards alongside provider/query, citation-domain, entity-gap, and claim-review evidence.
- [`query-intelligence.png`](query-intelligence.png) — proves that each provider/query execution
  exposes status, target mention, target citation, and normalized citation-domain counts.
- [`recommendations.png`](recommendations.png) — proves that ranked GEO actions include the observed
  problem, affected queries, provider evidence, and explicit current and target metrics.
- [`crawl-queued.png`](crawl-queued.png) — proves that an authorized public-site crawl enters a
  visible queued state while waiting for the Celery worker.
- [`crawl-succeeded.png`](crawl-succeeded.png) — proves that a completed crawl exposes its terminal
  status, page and error counts, completion time, and expandable crawl details.
- [`evidence-attached.png`](evidence-attached.png) — proves that the subsequent analysis reports the
  attached website-evidence page count for the active project.

Screens may contain browser chrome and public sample-project information. They contain no provider
keys or live-provider responses, and the deterministic Acme metrics are represented only by the
Acme demo screenshots.
