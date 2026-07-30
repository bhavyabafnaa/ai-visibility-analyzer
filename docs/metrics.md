# GeoLens metric definitions

## Status

These are proposed semantic contracts for future product work. No metric collection,
extraction, storage, or calculation is implemented in the foundation.

## Measurement units

- **Prompt execution:** one prompt evaluated against one configured provider/model at one
  point in time.
- **Eligible response:** a successfully completed prompt execution that can be analyzed.
  Errors and timeouts are excluded from metric denominators and must be reported separately.
- **Mention:** an explicit reference to a tracked entity in an eligible response.
- **Citation:** a source reference that can be normalized to a URL or domain.
- **Evaluation set:** the prompt executions selected by explicit filters such as time range,
  provider, model, locale, or prompt group.

Entity aliases, URL normalization, duplicate citations, and extraction confidence will need
versioned rules before these metrics become production contracts.

## Candidate metrics

### Mention rate

The percentage of eligible responses that mention the tracked entity at least once.

```text
mention_rate = responses_mentioning_entity / eligible_responses
```

A response counts once regardless of repeated mentions. The value is undefined when there
are no eligible responses.

### Citation rate

The percentage of eligible responses containing at least one citation to a tracked domain.

```text
citation_rate = responses_citing_domain / eligible_responses
```

A response counts once regardless of how many URLs from that domain it cites.

### Citation coverage

The percentage of responses that mention an entity and also cite one of its tracked domains.

```text
citation_coverage =
    responses_mentioning_entity_and_citing_domain / responses_mentioning_entity
```

This separates citation support from overall visibility. The value is undefined when the
entity has no mentions.

### Share of voice

The tracked entity's share of all distinct entity-response mentions in an evaluation set.

```text
share_of_voice =
    responses_mentioning_tracked_entity / sum(responses_mentioning_each_compared_entity)
```

The comparison set must be fixed and disclosed with the result. One response may contribute
to multiple entities.

### Source citation frequency

The percentage of eligible responses citing a normalized source at least once.

```text
source_citation_frequency = responses_citing_source / eligible_responses
```

The aggregation level—URL, registrable domain, or publisher—must accompany the result.

## Reporting requirements

Every future metric result should include:

- numerator, denominator, and percentage
- evaluation-set filters and time range
- provider and model identifiers as observed at execution time
- prompt and extraction rule versions
- sample size plus error/timeout counts
- an explicit `undefined` state instead of coercing empty denominators to zero

Metrics from different providers or time windows should not be compared unless the prompt set,
entity rules, and source normalization rules are compatible.
