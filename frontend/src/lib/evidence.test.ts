import { describe, expect, it } from "vitest";

import type {
  AnalysisBundle,
  AnalysisClaimResponse,
  ProjectResponse,
  PromptExecutionResponse,
} from "./api-types";
import {
  buildDashboardEvidence,
  isReservedExampleUrl,
  normalizeDomain,
  safeExternalUrl,
} from "./evidence";

const project: ProjectResponse = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Acme Cloud",
  aliases: [],
  site: null,
  competitors: [],
  created_at: "2026-07-30T08:00:00Z",
  updated_at: "2026-07-30T08:00:00Z",
};

function result(responseText: string): PromptExecutionResponse {
  return {
    provider: "mock",
    model_identifier: "mock-v1",
    prompt: "Test prompt",
    response_text: responseText,
    citations: [],
    raw_response: {},
    token_usage: {
      input_tokens: 1,
      output_tokens: 1,
      total_tokens: 2,
      cached_tokens: null,
      reasoning_tokens: null,
    },
    latency_ms: 1,
    status: "succeeded",
    error: null,
  };
}

function bundle(
  responseText: string,
  claims: AnalysisClaimResponse[] = [],
): AnalysisBundle {
  return {
    analysis: {
      analysis_id: "22222222-2222-4222-8222-222222222222",
      status: "succeeded",
      started_at: "2026-07-30T08:00:00Z",
      completed_at: "2026-07-30T08:00:01Z",
      persisted: true,
      results: [result(responseText)],
    },
    citations: [],
    entities: [],
    scores: [],
    claims,
  };
}

describe("dashboard evidence normalization", () => {
  it("uses separator-normalized whole-term entity matching", () => {
    const hyphenated = buildDashboardEvidence(project, bundle("Acme-Cloud is visible."));
    const substring = buildDashboardEvidence(
      { ...project, name: "Art" },
      bundle("Cart is visible."),
    );

    expect(hyphenated.comparisons[0]?.targetMentioned).toBe(true);
    expect(substring.comparisons[0]?.targetMentioned).toBe(false);
  });

  it("normalizes scheme-less domains and rejects active-content URLs", () => {
    expect(normalizeDomain("WWW.Example.com/path")).toBe("example.com");
    expect(normalizeDomain("javascript:alert(1)")).toBeNull();
    expect(safeExternalUrl("https://example.com/evidence")).toBe(
      "https://example.com/evidence",
    );
    expect(safeExternalUrl("javascript:alert(1)")).toBeNull();
  });

  it("identifies only parsed example hostnames as reserved demo URLs", () => {
    expect(isReservedExampleUrl("https://example/path")).toBe(true);
    expect(isReservedExampleUrl("https://acme.example/path")).toBe(true);
    expect(isReservedExampleUrl("https://acme.example./path")).toBe(true);
    expect(isReservedExampleUrl("https://example.com/acme.example")).toBe(false);
    expect(isReservedExampleUrl("https://notexample/path")).toBe(false);
  });

  it("does not present unconfigured claims as model-assisted risk", () => {
    const claim: AnalysisClaimResponse = {
      id: "33333333-3333-4333-8333-333333333333",
      response_id: "44444444-4444-4444-8444-444444444444",
      ordinal: 0,
      claim_text: "Acme Cloud is visible.",
      start_index: 0,
      end_index: 22,
      classification: "unverifiable",
      confidence: 0,
      explanation: "No classifier was requested.",
      classifier: "not_configured",
      model_identifier: null,
      response_prompt: "Test prompt",
      response_provider: "mock",
      segmentation_rule_version: "claim-segmentation-v1",
      evidence: [],
    };

    const evidence = buildDashboardEvidence(
      project,
      bundle("Acme Cloud is visible.", [claim]),
    );

    expect(evidence.claims[0]?.query).toBe("Test prompt");
    expect(evidence.claims[0]?.provider).toBe("mock");
    expect(evidence.recommendations.map((item) => item.id)).not.toContain("claim-risk");
  });
});
