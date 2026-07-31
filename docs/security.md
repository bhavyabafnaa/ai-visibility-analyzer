# Security notes

## Deployment boundary

GeoLens 0.1.0 is not safe as a directly internet-exposed service. It has no user identity or
tenant boundary. Keep the default loopback bindings or place the application behind TLS,
authentication, authorization, request-size limits, rate limiting, and network policy.

The default PostgreSQL password is development-only. Replace it and protect Redis before using
non-sample data. Do not commit `.env` files; only `.env.example` is tracked.

## Secrets and provider data

- Provider keys are `SecretStr` settings used only by backend adapters.
- Compose injects provider keys into the API only; the crawl worker does not receive them.
- The Next.js browser bundle receives no provider keys; the same-origin proxy uses a server-only
  API base URL.
- Logs and exception responses should not include keys. Operators must still review reverse-proxy,
  provider, and infrastructure logging.
- Prompts, provider answers, citations, raw provider JSON, crawl text, and model classifications
  are stored in PostgreSQL. Define encryption, backup, access, and deletion policies before using
  confidential data.
- Third-party calls may be retained or used according to each provider account and contract.

## SSRF controls

The crawler accepts only HTTP(S), rejects URL credentials and known metadata hosts, resolves every
origin, rejects every non-global address, pins the validated address for transport, sends the
original host/SNI, disables environment proxies, revalidates redirects, and stays on the exact
configured hostname. It also bounds redirects, bytes, time, pages, sitemaps, depth, and
concurrency.

These controls apply to the shipped HTTP crawler. Any future JavaScript renderer must enforce the
same policy for every navigation and subresource; validating only the final page URL is
insufficient.

Provider citation URLs are untrusted input. The backend contract accepts only credential-free
HTTP(S) citation URLs, and the frontend independently allowlists HTTP(S) before rendering an
external evidence link.

## Containers

The API, worker, and frontend run as non-root users and enable `no-new-privileges` in Compose.
PostgreSQL, Redis, API, worker, and frontend have health checks. Published ports bind to loopback
by default. The images do not include development tests or local environment files.

For an orchestrated production deployment, add read-only filesystems where compatible, resource
limits, network policies, secret mounts, image digest pinning, vulnerability scanning, signing,
and a serialized migration job.

## Reporting

Do not include real keys, prompts, stored responses, or customer URLs in public security reports.
Rotate any credential that may have been exposed and remove it from both current files and Git
history.
