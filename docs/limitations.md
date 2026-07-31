# Limitations

GeoLens 0.1.0 is a local/trusted-environment release candidate, not a finished
multi-tenant service.

## Security and operations

- There is no authentication, authorization, tenant isolation, audit log, rate
  limiting, TLS termination, or account lifecycle.
- The Compose defaults bind ports to loopback but use development database
  credentials and an unauthenticated Redis instance.
- Provider and analysis response bodies can contain sensitive business prompts
  or third-party content. PostgreSQL stores normalized artifacts and raw provider
  JSON without a retention policy or field-level encryption.
- No production observability stack, alerting, backup automation, disaster
  recovery procedure, or service-level objective is included.
- API-entrypoint migrations are appropriate for the single-API Compose topology.
  Multiple API replicas require a dedicated, serialized migration job.
- Image tags and Python dependency ranges are not a cryptographic software bill
  of materials or a fully reproducible supply-chain lock.
- The Compose deployment is intended for local evaluation. It should not be
  exposed directly to the public internet.

## Product behavior

- Provider analyses execute asynchronously through Celery. The API persists an
  analysis run, queues it through Redis, and returns HTTP 202 with a pending
  analysis identifier.
- The dashboard polls the analysis status until it reaches `succeeded`,
  `completed_with_errors`, or `failed`.
- There is no user-facing cancellation control, manual retry control, scheduled
  execution, or per-provider progress indicator for queued analyses.
- The dashboard presents the current analysis run but does not list, compare, or
  restore historical analysis runs.
- Analysis-run records preserve the provider and model identifiers selected when
  the job was queued. A worker configuration mismatch causes the job to fail
  rather than silently executing a different model.
- The dashboard attaches the active project's current succeeded crawl to the next
  analysis, but it does not list or select historical crawl jobs.
- The dashboard does not currently expose claim-classifier provider selection.
  Explicit claim-classifier selection remains available through the API.
- Recommendations use disclosed deterministic thresholds over one analysis run.
  They do not prove causality and cannot promise visibility, citation, traffic,
  ranking, or revenue changes.
- Entity extraction beyond configured brand and competitor aliases uses a
  capitalized-phrase heuristic rather than a general linguistic named-entity
  recognition model.
- Claim segmentation and evidence retrieval use lightweight deterministic rules.
  Classification, when explicitly enabled, remains provider judgment rather
  than independent ground truth.
- Metrics compare only the selected prompt and provider execution set. They are
  not statistically representative of an entire answer engine or all possible
  user queries.

## Crawler

- Only HTTP(S) HTML is extracted. A JavaScript renderer interface exists, but no
  renderer implementation is bundled.
- Crawls remain on the exact configured hostname; sibling subdomains are
  excluded.
- Page count, crawl depth, sitemap count, redirect count, response bytes, request
  timeout, and concurrency are bounded.
- Large websites are sampled rather than exhaustively indexed.
- Robots fetch failures are recorded and use the documented crawler fallback
  policy.
- The sample `.example` websites are intentionally non-routable and cannot be
  crawled.
- The crawler is designed for public websites that the user is authorized to
  access. It is not a general-purpose browser or authenticated-site crawler.

## Provider integrations

- Live adapters depend on third-party API availability, credentials, quotas,
  model access, commercial terms, and response schemas.
- Model identifiers are environment-configured and must match models enabled for
  the developer's provider account.
- Live provider availability may change independently of GeoLens.
- Recorded fixtures validate known response structures but cannot guarantee
  compatibility with future provider schema changes.
- Live contract tests are opt-in and are not run in CI because they create
  external traffic and may incur cost.
- Consumer products such as ChatGPT, Gemini, and Perplexity may produce different
  results from their corresponding APIs because product prompts, models, search
  behavior, personalization, and configurations can differ.

See [provider-disclaimer.md](provider-disclaimer.md) and
[security.md](security.md) before deploying GeoLens or enabling live providers.
