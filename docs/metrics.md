# GeoLens analysis and metric contracts

## Status

These contracts are implemented by the framework-independent `geolens_api.analysis` package.
Persisted results record the applicable rule version. Deterministic scoring is separate from
model-assisted claim classification and can be reproduced without a provider, database,
FastAPI, or Redis.

## Measurement units and eligibility

- **Prompt execution:** one prompt evaluated against one configured provider/model at one
  point in time.
- **Eligible response:** a prompt execution whose provider status is `succeeded`. Errors,
  timeouts, rate limits, and disabled providers are excluded from metric denominators.
- **Mention:** a whole-term match for a configured entity name or alias.
- **Citation occurrence:** a provider citation whose URL has a valid normalized hostname.
- **Response/domain occurrence:** one normalized hostname in one eligible response. Duplicate
  citations to the same hostname in the response count once where this unit is used.
- **Evaluation set:** the persisted prompt executions in one analysis run.

Every metric result stores its numerator, denominator, ratio (`value`), percentage, defined
state, method, and rule version. A zero denominator produces `value = null`,
`percentage = null`, and `is_defined = false`; it is never coerced to zero.

## Deterministic extraction rules

### Brand, alias, and competitor matching

Configured project and competitor names and aliases use Unicode NFKC normalization,
case-folding, separator normalization, and whole-term boundaries. For example, `Acme Cloud`
matches `ACME-Cloud`, while the alias `Art` does not match `Cart`. Overlapping aliases for the
same entity are resolved to the longest match. Matching returns the original response offsets.

Current rule version: `mention-v1`.

### Mention position

Only the first matched character position is used:

```text
relative_mention_position =
    first_mention_character_index / max(response_character_length, 1)
```

The reporting bucket is `early` for values below `1/3`, `middle` below `2/3`, and `late`
otherwise. A response without a match has no mention position.

### Citation-domain normalization

The citation URL hostname is lowercased, normalized to ASCII IDNA, stripped of a trailing dot,
and stripped of only a leading `www.`. Ports, paths, queries, and fragments do not affect the
domain. Invalid or missing hostnames have no normalized domain. A target domain matches itself
and its subdomains, but not suffix lookalikes such as `example.com.attacker.test`.

The stored aggregation level is normalized hostname, not registrable domain or publisher.
Current rule version: `citation-domain-v1`.

### Entity extraction

Configured target and competitor entities use the alias matcher. Additional candidates use a
deterministic capitalized-phrase rule and never duplicate a configured-entity span. Each entity
record stores its mention spans, matched aliases, first position, kind, extraction method, and
rule version.

This lightweight rule is reproducible extraction, not general-purpose linguistic NER. Current
rule version: `entity-v1`.

## Deterministic metric formulas

All ratios range from 0 to 1; `percentage = value * 100`.

### Visibility rate

```text
visibility_rate =
    eligible responses mentioning the target /
    eligible responses
```

A response counts once regardless of repeated target mentions.

### Target-domain citation coverage

```text
target_domain_citation_coverage =
    eligible responses mentioning the target and citing the target domain /
    eligible responses mentioning the target
```

A target-domain citation includes any normalized subdomain. The result is undefined when the
target has no mentions or the project has no target site.

### Citation share

```text
citation_share =
    target-domain response/domain occurrences /
    all response/domain occurrences in eligible responses
```

Duplicate citations to one normalized hostname in one response count once. Distinct target
subdomains are distinct response/domain occurrences. The result is undefined when there are no
normalized citations or the project has no target site.

### Rank-weighted share of AI voice

Within each eligible response, the target and configured competitors are ordered by first
mention character position. A deterministic entity-key tie-break resolves equal positions.
Each mentioned entity receives reciprocal-rank weight:

```text
entity_weight(response, entity) = 1 / first_mention_rank

rank_weighted_share_of_ai_voice =
    sum(target entity weights across eligible responses) /
    sum(all target and competitor weights across eligible responses)
```

Repeated mentions do not add weight. The comparison set is the target plus the competitors
stored on the project. The result is undefined when none of those entities is mentioned.

### Entity coverage

```text
entity_coverage =
    observed eligible response/tracked-entity pairs /
    (eligible responses * configured tracked entities)
```

Tracked entities are the target and configured competitors. Each response/entity pair counts
once. The result is undefined for no eligible responses or an empty tracked set.

Current formula version for all five deterministic metrics: `metrics-v1`.

## Claim-support analysis

Claim support has three explicit stages:

1. deterministic claim segmentation;
2. deterministic evidence retrieval from selected crawl pages and persisted provider citations;
3. model-assisted classification behind the `ClaimClassifier` boundary.

The model classifier never calculates visibility, citation, entity, position, rank, retrieval,
or aggregate-risk scores.

### Claim segmentation

Responses are segmented at sentence, semicolon, and newline boundaries. Questions, fragments
with fewer than three word tokens, explicit first-person opinions, and simple recommendation
prefixes are excluded. Each stored claim retains response offsets and ordinal.

Current rule version: `claim-segmentation-v1`.

### Evidence retrieval

Crawl-page main text and persisted citation `cited_text` are split into stable chunks of at
most 800 characters. For a claim token `t`, across `N` available chunks:

```text
idf(t) = ln((1 + N) / (1 + document_frequency(t))) + 1

weighted_claim_coverage =
    sum(idf(t) for overlapping claim tokens) /
    sum(idf(t) for all claim tokens)

jaccard =
    overlapping unique tokens /
    union of unique claim and evidence tokens

evidence_relevance = 0.7 * weighted_claim_coverage + 0.3 * jaccard
```

Up to five chunks with `evidence_relevance >= 0.05` are retained, ordered by descending score
and stable evidence reference. Stored references identify the crawl page or citation and chunk.
Current rule version: `evidence-retrieval-v1`.

### Model-assisted classification

When `claim_classifier_provider` is supplied, that provider receives one claim and its retrieved
evidence and must return:

- `supported`
- `partially_supported`
- `unsupported`
- `contradicted`
- `unverifiable`

The stored result includes classification, confidence from 0 to 1, explanation, provider/model,
and evidence references. Provider failures or invalid structured output fail closed to
`unverifiable` with zero confidence. No provider call is made when retrieval found no relevant
stored evidence; that claim is also `unverifiable`. If no classifier is requested, claims are
explicitly stored as not model-classified and `unverifiable`; no hidden provider call is made.

### Aggregate claim-support risk

Classification labels have disclosed risk weights:

```text
supported = 0.0
partially_supported = 0.4
unsupported = 0.8
contradicted = 1.0
unverifiable = 0.6
```

For model confidence `c` and label weight `w`, low confidence moves the contribution toward the
unverifiable weight:

```text
claim_risk = c * w + (1 - c) * 0.6

aggregate_claim_support_risk =
    sum(claim_risk) / classified_claim_count
```

The aggregate is undefined when no claims were segmented. Current rule version:
`claim-risk-v1`.

The aggregate is always returned with `is_objective_truth = false` and this disclosure:

> This model-assisted claim-support risk estimate is not objective truth; it depends on
> available evidence and classifier judgment.

The score is a prioritization aid. It is not a factuality probability, legal conclusion, or
independent ground truth.

## Reporting and comparison requirements

Comparisons should use compatible provider/model identifiers, prompt sets, project entity
configuration, crawl selection, and rule versions. API consumers should report failed execution
counts alongside eligible sample size and must retain the risk disclosure anywhere the
claim-support aggregate is displayed.
