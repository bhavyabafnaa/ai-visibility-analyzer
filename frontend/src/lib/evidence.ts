import type {
  AnalysisBundle,
  AnalysisClaimResponse,
  AnalysisScoreResponse,
  ProjectResponse,
  PromptExecutionResponse,
} from "./api-types";

export interface QueryComparison {
  id: string;
  query: string;
  provider: string;
  model: string;
  status: PromptExecutionResponse["status"];
  targetMentioned: boolean;
  targetCited: boolean;
  citationDomains: string[];
  competitors: string[];
  latencyMs: number;
  error: string | null;
}

export interface CitationDomainBreakdown {
  domain: string;
  citations: number;
  queryCount: number;
  providers: string[];
  isTarget: boolean;
  share: number;
}

export interface EntityGap {
  entity: string;
  mentionQueries: number;
  targetMissingQueries: number;
  leadsTargetQueries: number;
  affectedQueries: string[];
  providers: string[];
}

export interface OverviewMetric {
  name: string;
  shortName: string;
  value: number | null;
  numerator: number;
  denominator: number;
  detail: string;
  tone: "positive" | "warning" | "critical" | "neutral";
}

export interface EvidenceRecommendation {
  id: string;
  rank: number;
  observedProblem: string;
  affectedQueries: string[];
  providerEvidence: string[];
  recommendedAction: string;
  expectedMetric: {
    name: string;
    baseline: string;
    target: string;
  };
  priority: "High" | "Medium" | "Low";
  confidence: "High" | "Medium" | "Low";
  score: number;
}

export interface ClaimWithContext extends AnalysisClaimResponse {
  query: string;
  provider: string;
}

export interface DashboardEvidence {
  comparisons: QueryComparison[];
  citationDomains: CitationDomainBreakdown[];
  entityGaps: EntityGap[];
  metrics: OverviewMetric[];
  recommendations: EvidenceRecommendation[];
  claims: ClaimWithContext[];
  eligibleCount: number;
  failedCount: number;
}

function escaped(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function containsAlias(text: string, aliases: string[]): boolean {
  return aliases.some((alias) => {
    const trimmed = alias.trim();
    if (!trimmed) return false;
    return new RegExp(`(^|[^\\p{L}\\p{N}])${escaped(trimmed)}([^\\p{L}\\p{N}]|$)`, "iu").test(
      text,
    );
  });
}

function firstAliasIndex(text: string, aliases: string[]): number | null {
  const normalized = text.toLocaleLowerCase();
  const indexes = aliases
    .map((alias) => normalized.indexOf(alias.toLocaleLowerCase()))
    .filter((index) => index >= 0);
  return indexes.length ? Math.min(...indexes) : null;
}

export function normalizeDomain(url: string): string | null {
  try {
    return new URL(url).hostname.toLocaleLowerCase().replace(/\.$/, "").replace(/^www\./, "");
  } catch {
    return null;
  }
}

function matchesTargetDomain(domain: string | null, targetDomain: string | null): boolean {
  if (!domain || !targetDomain) return false;
  return domain === targetDomain || domain.endsWith(`.${targetDomain}`);
}

function scoreByName(scores: AnalysisScoreResponse[], name: string) {
  return scores.find((score) => score.name === name);
}

function metricValue(
  scores: AnalysisScoreResponse[],
  name: string,
  fallbackNumerator: number,
  fallbackDenominator: number,
) {
  const persisted = scoreByName(scores, name);
  if (persisted) {
    return {
      value: persisted.value,
      numerator: persisted.numerator,
      denominator: persisted.denominator,
    };
  }
  return {
    value: fallbackDenominator ? fallbackNumerator / fallbackDenominator : null,
    numerator: fallbackNumerator,
    denominator: fallbackDenominator,
  };
}

function toneFor(value: number | null, warning: number, positive: number) {
  if (value === null) return "neutral" as const;
  if (value >= positive) return "positive" as const;
  if (value >= warning) return "warning" as const;
  return "critical" as const;
}

function formatPercent(value: number | null) {
  return value === null ? "Not defined" : `${Math.round(value * 100)}%`;
}

function unique<T>(values: T[]): T[] {
  return Array.from(new Set(values));
}

function summarizeQuery(query: string): string {
  return query.length > 76 ? `${query.slice(0, 73)}…` : query;
}

export function buildDashboardEvidence(
  project: ProjectResponse,
  bundle: AnalysisBundle,
): DashboardEvidence {
  const { analysis, scores, claims } = bundle;
  const targetAliases = [project.name, ...project.aliases];
  const targetDomain = project.site ? normalizeDomain(project.site.url) : null;
  const competitors = project.competitors.map((competitor) => ({
    name: competitor.name,
    aliases: [competitor.name, ...competitor.aliases],
  }));

  const comparisons = analysis.results.map((result, index): QueryComparison => {
    const domains = unique(
      result.citations
        .map((citation) => normalizeDomain(citation.url))
        .filter((domain): domain is string => domain !== null),
    );
    return {
      id: `${result.provider}-${index}`,
      query: result.prompt,
      provider: result.provider,
      model: result.model_identifier,
      status: result.status,
      targetMentioned: containsAlias(result.response_text, targetAliases),
      targetCited: domains.some((domain) => matchesTargetDomain(domain, targetDomain)),
      citationDomains: domains,
      competitors: competitors
        .filter((competitor) => containsAlias(result.response_text, competitor.aliases))
        .map((competitor) => competitor.name),
      latencyMs: result.latency_ms,
      error: result.error?.message ?? null,
    };
  });

  const eligible = comparisons.filter((row) => row.status === "succeeded");
  const failedCount = comparisons.length - eligible.length;
  const mentioned = eligible.filter((row) => row.targetMentioned);
  const targetCited = mentioned.filter((row) => row.targetCited);

  const responseDomainOccurrences = eligible.flatMap((row) =>
    row.citationDomains.map((domain) => ({ row, domain })),
  );
  const targetOccurrences = responseDomainOccurrences.filter(({ domain }) =>
    matchesTargetDomain(domain, targetDomain),
  );

  let targetVoiceWeight = 0;
  let allVoiceWeight = 0;
  let observedEntityPairs = 0;
  for (const result of analysis.results.filter((item) => item.status === "succeeded")) {
    const ranked = [
      {
        key: "target",
        index: firstAliasIndex(result.response_text, targetAliases),
      },
      ...competitors.map((competitor) => ({
        key: competitor.name,
        index: firstAliasIndex(result.response_text, competitor.aliases),
      })),
    ]
      .filter((item): item is { key: string; index: number } => item.index !== null)
      .sort((left, right) => left.index - right.index || left.key.localeCompare(right.key));
    observedEntityPairs += ranked.length;
    ranked.forEach((item, index) => {
      const weight = 1 / (index + 1);
      allVoiceWeight += weight;
      if (item.key === "target") targetVoiceWeight += weight;
    });
  }

  const visibility = metricValue(scores, "visibility_rate", mentioned.length, eligible.length);
  const citationCoverage = metricValue(
    scores,
    "target_domain_citation_coverage",
    targetCited.length,
    mentioned.length,
  );
  const citationShare = metricValue(
    scores,
    "citation_share",
    targetOccurrences.length,
    responseDomainOccurrences.length,
  );
  const shareOfVoice = metricValue(
    scores,
    "rank_weighted_share_of_ai_voice",
    targetVoiceWeight,
    allVoiceWeight,
  );
  const trackedEntities = competitors.length + 1;
  const entityCoverage = metricValue(
    scores,
    "entity_coverage",
    observedEntityPairs,
    eligible.length * trackedEntities,
  );
  const claimRisk = scoreByName(scores, "claim_support_risk");

  const metrics: OverviewMetric[] = [
    {
      name: "Visibility rate",
      shortName: "Visibility",
      ...visibility,
      detail: `${visibility.numerator} of ${visibility.denominator} eligible answers mention ${project.name}`,
      tone: toneFor(visibility.value, 0.6, 0.8),
    },
    {
      name: "Target citation coverage",
      shortName: "Citation coverage",
      ...citationCoverage,
      detail: `${citationCoverage.numerator} of ${citationCoverage.denominator} brand mentions cite the target domain`,
      tone: toneFor(citationCoverage.value, 0.5, 0.75),
    },
    {
      name: "Citation share",
      shortName: "Citation share",
      ...citationShare,
      detail: `${citationShare.numerator} of ${citationShare.denominator} response-domain occurrences`,
      tone: toneFor(citationShare.value, 0.3, 0.55),
    },
    {
      name: "Rank-weighted share of AI voice",
      shortName: "AI share of voice",
      ...shareOfVoice,
      detail: "Reciprocal rank across target and configured competitors",
      tone: toneFor(shareOfVoice.value, 0.4, 0.6),
    },
    {
      name: "Entity coverage",
      shortName: "Entity coverage",
      ...entityCoverage,
      detail: `${entityCoverage.numerator} of ${entityCoverage.denominator} eligible response/entity pairs`,
      tone: toneFor(entityCoverage.value, 0.45, 0.7),
    },
  ];

  const domainMap = new Map<
    string,
    { citations: number; queries: Set<string>; providers: Set<string> }
  >();
  for (const result of analysis.results.filter((item) => item.status === "succeeded")) {
    for (const citation of result.citations) {
      const domain = normalizeDomain(citation.url);
      if (!domain) continue;
      const current = domainMap.get(domain) ?? {
        citations: 0,
        queries: new Set<string>(),
        providers: new Set<string>(),
      };
      current.citations += 1;
      current.queries.add(result.prompt);
      current.providers.add(result.provider);
      domainMap.set(domain, current);
    }
  }
  const totalCitations = Array.from(domainMap.values()).reduce(
    (sum, current) => sum + current.citations,
    0,
  );
  const citationDomains = Array.from(domainMap.entries())
    .map(([domain, current]): CitationDomainBreakdown => ({
      domain,
      citations: current.citations,
      queryCount: current.queries.size,
      providers: Array.from(current.providers),
      isTarget: matchesTargetDomain(domain, targetDomain),
      share: totalCitations ? current.citations / totalCitations : 0,
    }))
    .sort(
      (left, right) =>
        right.citations - left.citations || Number(right.isTarget) - Number(left.isTarget),
    );

  const entityGaps = competitors.map((competitor): EntityGap => {
    const matchingResults = analysis.results.filter(
      (result) =>
        result.status === "succeeded" && containsAlias(result.response_text, competitor.aliases),
    );
    const missing = matchingResults.filter(
      (result) => !containsAlias(result.response_text, targetAliases),
    );
    const leading = matchingResults.filter((result) => {
      const competitorIndex = firstAliasIndex(result.response_text, competitor.aliases);
      const targetIndex = firstAliasIndex(result.response_text, targetAliases);
      return (
        competitorIndex !== null && (targetIndex === null || competitorIndex < targetIndex)
      );
    });
    return {
      entity: competitor.name,
      mentionQueries: unique(matchingResults.map((result) => result.prompt)).length,
      targetMissingQueries: unique(missing.map((result) => result.prompt)).length,
      leadsTargetQueries: unique(leading.map((result) => result.prompt)).length,
      affectedQueries: unique(missing.map((result) => result.prompt)),
      providers: unique(missing.map((result) => result.provider)),
    };
  });

  const claimsWithContext = claims.map((claim): ClaimWithContext => {
    const result = analysis.results.find((candidate) =>
      candidate.response_text.includes(claim.claim_text),
    );
    return {
      ...claim,
      query: result?.prompt ?? `Response ${claim.response_id.slice(0, 8)}`,
      provider: result?.provider ?? claim.classifier,
    };
  });

  const recommendations: Omit<EvidenceRecommendation, "rank">[] = [];
  const failed = comparisons.filter((row) => row.status !== "succeeded");
  if (failed.length) {
    recommendations.push({
      id: "provider-coverage",
      observedProblem: `${failed.length} of ${comparisons.length} provider-query executions were ineligible because they did not succeed.`,
      affectedQueries: unique(failed.map((row) => summarizeQuery(row.query))),
      providerEvidence: unique(
        failed.map(
          (row) =>
            `${row.provider} · ${row.status}${row.error ? ` · ${row.error}` : ""}`,
        ),
      ),
      recommendedAction:
        "Restore the named provider configuration, then re-run only the affected query-provider cells so denominator coverage is comparable.",
      expectedMetric: {
        name: "Eligible provider coverage",
        baseline: `${comparisons.length - failed.length}/${comparisons.length}`,
        target: `${comparisons.length}/${comparisons.length}`,
      },
      priority: "High",
      confidence: "High",
      score: 100 + failed.length,
    });
  }

  const uncitedMentionRows = eligible.filter((row) => row.targetMentioned && !row.targetCited);
  if (
    citationCoverage.value !== null &&
    citationCoverage.value < 0.75 &&
    uncitedMentionRows.length
  ) {
    recommendations.push({
      id: "target-citation-coverage",
      observedProblem: `${project.name} is mentioned without a target-domain citation in ${uncitedMentionRows.length} eligible provider-query answer${uncitedMentionRows.length === 1 ? "" : "s"}.`,
      affectedQueries: unique(uncitedMentionRows.map((row) => summarizeQuery(row.query))),
      providerEvidence: uncitedMentionRows.slice(0, 4).map((row) => {
        const cited = row.citationDomains.length
          ? row.citationDomains.join(", ")
          : "no normalized citation domains";
        return `${row.provider} cited ${cited}, but not ${targetDomain ?? "the target domain"}`;
      }),
      recommendedAction: `Create or strengthen first-party evidence pages that directly answer the listed queries, using the exact capabilities already attributed to ${project.name} in provider answers and adding verifiable primary proof.`,
      expectedMetric: {
        name: "Target citation coverage",
        baseline: formatPercent(citationCoverage.value),
        target: "≥75%",
      },
      priority: "High",
      confidence: "High",
      score: 92 + uncitedMentionRows.length,
    });
  }

  const largestGap = [...entityGaps].sort(
    (left, right) =>
      right.targetMissingQueries - left.targetMissingQueries ||
      right.leadsTargetQueries - left.leadsTargetQueries,
  )[0];
  if (largestGap && largestGap.targetMissingQueries > 0) {
    recommendations.push({
      id: `entity-gap-${largestGap.entity}`,
      observedProblem: `${largestGap.entity} appears while ${project.name} is absent in ${largestGap.targetMissingQueries} tracked quer${largestGap.targetMissingQueries === 1 ? "y" : "ies"} and leads it in ${largestGap.leadsTargetQueries}.`,
      affectedQueries: largestGap.affectedQueries.map(summarizeQuery),
      providerEvidence: largestGap.providers.map(
        (provider) =>
          `${provider} mentioned ${largestGap.entity} without a matched ${project.name} alias`,
      ),
      recommendedAction: `Build a query-specific comparison asset for ${project.name} versus ${largestGap.entity}, covering the capabilities named in the affected prompts and backing each differentiator with citable evidence.`,
      expectedMetric: {
        name: "Entity gap",
        baseline: `${largestGap.targetMissingQueries} missing-query gap`,
        target: "0 missing-query gaps",
      },
      priority: largestGap.targetMissingQueries > 1 ? "High" : "Medium",
      confidence: "High",
      score: 84 + largestGap.targetMissingQueries * 3,
    });
  }

  if (citationShare.value !== null && citationShare.value < 0.4) {
    const nonTargetDomains = citationDomains.filter((domain) => !domain.isTarget).slice(0, 3);
    recommendations.push({
      id: "citation-share",
      observedProblem: `The target domain accounts for ${formatPercent(citationShare.value)} of normalized response-domain occurrences; ${nonTargetDomains.map((domain) => domain.domain).join(", ")} receive the largest competing share.`,
      affectedQueries: unique(
        eligible
          .filter((row) => row.citationDomains.some((domain) => !matchesTargetDomain(domain, targetDomain)))
          .map((row) => summarizeQuery(row.query)),
      ),
      providerEvidence: nonTargetDomains.map(
        (domain) =>
          `${domain.domain}: ${domain.citations} citation${domain.citations === 1 ? "" : "s"} across ${domain.queryCount} quer${domain.queryCount === 1 ? "y" : "ies"}`,
      ),
      recommendedAction: `Prioritize outreach or source inclusion on the observed high-share domains, and supply them with verifiable ${project.name} data tailored to the listed query themes.`,
      expectedMetric: {
        name: "Citation share",
        baseline: formatPercent(citationShare.value),
        target: "≥40%",
      },
      priority: citationShare.value < 0.25 ? "High" : "Medium",
      confidence: "High",
      score: 76 + Math.round((0.4 - citationShare.value) * 20),
    });
  }

  const riskyClaims = claimsWithContext.filter(
    (claim) => !["supported", "partially_supported"].includes(claim.classification),
  );
  if (riskyClaims.length) {
    const topClaims = [...riskyClaims]
      .sort((left, right) => right.confidence - left.confidence)
      .slice(0, 3);
    recommendations.push({
      id: "claim-risk",
      observedProblem: `${riskyClaims.length} extracted claim${riskyClaims.length === 1 ? " is" : "s are"} unsupported, contradicted, or unverifiable against the stored evidence set.`,
      affectedQueries: unique(topClaims.map((claim) => summarizeQuery(claim.query))),
      providerEvidence: topClaims.map((claim) => {
        const source = claim.evidence[0]?.source_reference ?? "no relevant stored evidence";
        return `${claim.provider} · ${claim.classification} (${Math.round(claim.confidence * 100)}% classifier confidence) · ${source}`;
      }),
      recommendedAction:
        "Review the named answer claims against the surfaced evidence excerpts; add primary-source proof for accurate claims and correct contradicted wording before the next run.",
      expectedMetric: {
        name: "Claim-support risk",
        baseline: claimRisk?.value === null ? "Not defined" : formatPercent(claimRisk?.value ?? null),
        target: "<30%",
      },
      priority: riskyClaims.some((claim) => claim.classification === "contradicted")
        ? "High"
        : "Medium",
      confidence: riskyClaims.some((claim) => claim.evidence.length) ? "Medium" : "Low",
      score: 68 + riskyClaims.length,
    });
  }

  if (!recommendations.length) {
    recommendations.push({
      id: "maintain-coverage",
      observedProblem: `No threshold breach was found across ${eligible.length} eligible execution${eligible.length === 1 ? "" : "s"} in this run.`,
      affectedQueries: unique(eligible.map((row) => summarizeQuery(row.query))),
      providerEvidence: unique(
        eligible.map((row) => `${row.provider} · succeeded · ${row.citationDomains.length} domains`),
      ),
      recommendedAction:
        "Preserve this prompt set as the comparison baseline and investigate only changes that move a measured metric beyond its current value.",
      expectedMetric: {
        name: "Visibility rate",
        baseline: formatPercent(visibility.value),
        target: `Maintain ≥${formatPercent(visibility.value)}`,
      },
      priority: "Low",
      confidence: "High",
      score: 10,
    });
  }

  const rankedRecommendations = recommendations
    .sort((left, right) => right.score - left.score)
    .map((recommendation, index) => ({ ...recommendation, rank: index + 1 }));

  return {
    comparisons,
    citationDomains,
    entityGaps,
    metrics,
    recommendations: rankedRecommendations,
    claims: claimsWithContext,
    eligibleCount: eligible.length,
    failedCount,
  };
}

export function displayPercent(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}%`;
}
