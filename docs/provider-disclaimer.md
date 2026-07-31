# Provider and API disclaimer

GeoLens is an independent project. OpenAI, Gemini/Google, and Perplexity names identify optional
third-party integrations; their use does not imply sponsorship, endorsement, certification, or
affiliation.

Provider APIs, endpoint paths, model identifiers, tool availability, citation formats, quotas,
pricing, regional availability, safety behavior, retention, and terms can change without a
GeoLens release. The checked-in defaults and recorded fixtures describe the adapter contract at
the time of the 0.1.0 release; they are not a guarantee that an account can access a named model
or that a future response will retain the same shape.

Model identifiers are environment-configured and must be set to models enabled for the developer's provider account. Provider model availability may change.

Before enabling a live provider:

1. verify the current provider documentation and terms for the configured account and region;
2. choose an available model identifier rather than assuming the sample default is available;
3. understand that web search and model calls may incur charges;
4. confirm how prompts, evidence excerpts, outputs, and metadata are retained or used;
5. run the opt-in live contract test in a non-production account;
6. monitor provider errors and disable the adapter if its response contract changes.

Provider answers and citations can be incomplete, stale, biased, incorrect, or fabricated.
Normalized output is evidence for review, not an endorsement or factual guarantee. GeoLens
metrics describe only the configured run, and recommendations do not promise changes in answer
engine behavior.

Verification references as of the 0.1.0 release:

- [OpenAI Responses web search](https://platform.openai.com/docs/guides/tools-web-search)
- [Gemini Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview)
- [Gemini grounding with Google Search](https://ai.google.dev/gemini-api/docs/google-search)
- [Perplexity Sonar API reference](https://docs.perplexity.ai/api-reference/sonar-post)
