# Limitations

GeoLens 0.1.0 is a local/trusted-environment release candidate, not a finished multi-tenant
service.

## Security and operations

- There is no authentication, authorization, tenant isolation, audit log, rate limiting, TLS
  termination, or account lifecycle.
- The Compose defaults bind ports to loopback but use development database credentials and an
  unauthenticated Redis instance.
- Provider and analysis response bodies can contain sensitive business prompts or third-party
  content. PostgreSQL stores normalized artifacts and raw provider JSON without a retention
  policy or field-level encryption.
- No production observability stack, alerting, backup automation, disaster recovery, or SLO is
  included.
- API-entrypoint migrations are appropriate for the single-API Compose topology. Multiple API
  replicas require a dedicated, serialized migration job.
- Image tags and Python dependency ranges are not a cryptographic software bill of materials or
  a fully reproducible supply-chain lock.

## Product behavior

- Analyses run synchronously in the API request rather than through Celery. The client connection
  must remain open, and large provider/query matrices can approach the configured provider timeout
  and retry budget or an upstream proxy timeout. There is no background retry, progress polling,
  or recovery for an interrupted analysis request in v0.1.
- The dashboard presents the current in-memory run; it does not list or restore historical runs.
- The dashboard attaches the active project's current succeeded crawl to the next analysis, but it
  does not list or select historical crawl jobs and does not select a claim-classifier provider.
  Historical crawl selection and claim-classifier selection remain API-only capabilities.
- Recommendations use disclosed deterministic thresholds over one run. They do not prove
  causality and cannot promise visibility, citation, traffic, or revenue changes.
- Entity extraction beyond configured aliases is a capitalized-phrase heuristic, not general
  linguistic named-entity recognition.
- Claim segmentation and retrieval are lightweight deterministic rules. Classification, when
  explicitly enabled, remains provider judgment rather than ground truth.
- Metrics compare only the selected prompt/provider execution set. They are not statistically
  representative of an entire answer engine.

## Crawler

- Only HTTP(S) HTML is extracted. A JavaScript renderer interface exists, but no renderer is
  shipped.
- Crawls remain on the exact configured hostname; sibling subdomains are excluded.
- Page count, depth, sitemap count, redirect count, response bytes, timeout, and concurrency are
  bounded. Large sites will be sampled rather than exhaustively indexed.
- Robots fetch failures are recorded and use the documented crawler fallback policy.
- The sample `.example` sites are intentionally non-routable and cannot be crawled.

## Provider integrations

- Live adapters depend on third-party API availability, credentials, quotas, model access, terms,
  and response schemas.
- Model identifiers are environment-configured and must match models enabled for the developer's
  provider account; availability may change independently of GeoLens.
- Recorded fixtures validate known response shapes but cannot guarantee future provider
  compatibility.
- Live contract tests are opt-in and are not run in CI.

See [provider-disclaimer.md](provider-disclaimer.md) and [security.md](security.md) before deploying
or enabling live providers.
