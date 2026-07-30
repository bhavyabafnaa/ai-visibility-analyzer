import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  AnalysisClaimResponse,
  AnalysisStartResponse,
  ProjectResponse,
  ProviderAvailabilityResponse,
} from "@/lib/api-types";

import { Dashboard } from "./dashboard";

const providers: ProviderAvailabilityResponse[] = [
  {
    name: "mock",
    model_identifier: "mock-v1",
    enabled: true,
    disabled_reason: null,
  },
  {
    name: "openai",
    model_identifier: "gpt-test",
    enabled: false,
    disabled_reason: "OPENAI_API_KEY is not configured",
  },
];

const project: ProjectResponse = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Acme Cloud",
  aliases: ["Acme"],
  site: {
    id: "22222222-2222-4222-8222-222222222222",
    project_id: "11111111-1111-4111-8111-111111111111",
    url: "https://acme.example/",
    created_at: "2026-07-30T08:00:00Z",
    updated_at: "2026-07-30T08:00:00Z",
  },
  competitors: [
    {
      id: "33333333-3333-4333-8333-333333333333",
      project_id: "11111111-1111-4111-8111-111111111111",
      name: "Northstar AI",
      aliases: ["Northstar"],
      url: "https://northstar.example/",
      created_at: "2026-07-30T08:00:00Z",
      updated_at: "2026-07-30T08:00:00Z",
    },
  ],
  created_at: "2026-07-30T08:00:00Z",
  updated_at: "2026-07-30T08:00:00Z",
};

function response(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Dashboard", () => {
  it("creates a configured project from the onboarding flow", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/geolens/projects") && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as {
          name: string;
          aliases: string[];
          competitors: Array<{ name: string }>;
        };
        expect(body.name).toBe("Orbit Labs");
        expect(body.aliases).toEqual(["Orbit", "Orbit AI"]);
        expect(body.competitors[0]?.name).toBe("Northstar AI");
        return response({ ...project, name: "Orbit Labs", aliases: body.aliases }, 201);
      }
      if (url.endsWith("/api/geolens/projects")) return response([]);
      if (url.endsWith("/api/geolens/providers")) return response(providers);
      return response({ detail: "Unexpected request" }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Dashboard />);

    expect(await screen.findByRole("heading", { name: "Set up your first project" })).toBeVisible();
    const name = screen.getByLabelText("Project / brand name");
    await user.clear(name);
    await user.type(name, "Orbit Labs");
    const aliases = screen.getByLabelText("Brand aliases");
    await user.clear(aliases);
    await user.type(aliases, "Orbit, Orbit AI");
    await user.click(screen.getByRole("button", { name: "Create project & continue" }));

    expect(await screen.findByRole("heading", { name: "Orbit Labs overview" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Queries to analyze" })).toBeVisible();
    expect(screen.getByText("MockProvider")).toBeVisible();
  });

  it("runs the query matrix and renders recommendations from calculated evidence", async () => {
    const user = userEvent.setup();
    const analysis: AnalysisStartResponse = {
      analysis_id: "44444444-4444-4444-8444-444444444444",
      status: "succeeded",
      started_at: "2026-07-30T09:00:00.000Z",
      completed_at: "2026-07-30T09:00:00.025Z",
      persisted: true,
      results: [
        {
          provider: "mock",
          model_identifier: "mock-v1",
          prompt: "What are the best AI visibility platforms for B2B teams?",
          response_text: "Northstar AI leads B2B shortlists. Acme Cloud offers citation monitoring.",
          citations: [
            {
              url: "https://northstar.example/guide",
              title: "Guide",
              start_index: null,
              end_index: null,
              cited_text: "Northstar AI leads B2B shortlists.",
              published_at: null,
            },
          ],
          raw_response: {},
          token_usage: {
            input_tokens: 10,
            output_tokens: 12,
            total_tokens: 22,
            cached_tokens: null,
            reasoning_tokens: null,
          },
          latency_ms: 12,
          status: "succeeded",
          error: null,
        },
        {
          provider: "mock",
          model_identifier: "mock-v1",
          prompt: "Compare Acme Cloud with Northstar AI for citation monitoring.",
          response_text: "Northstar AI provides broad citation monitoring for marketing teams.",
          citations: [
            {
              url: "https://northstar.example/product",
              title: "Northstar",
              start_index: null,
              end_index: null,
              cited_text: "Northstar AI provides broad citation monitoring.",
              published_at: null,
            },
          ],
          raw_response: {},
          token_usage: {
            input_tokens: 10,
            output_tokens: 10,
            total_tokens: 20,
            cached_tokens: null,
            reasoning_tokens: null,
          },
          latency_ms: 10,
          status: "succeeded",
          error: null,
        },
      ],
    };
    const claims: AnalysisClaimResponse[] = [
      {
        id: "55555555-5555-4555-8555-555555555555",
        response_id: "66666666-6666-4666-8666-666666666666",
        ordinal: 0,
        claim_text: "Northstar AI provides broad citation monitoring for marketing teams.",
        start_index: 0,
        end_index: 68,
        classification: "unverifiable",
        confidence: 0,
        explanation: "Claim classification was not configured.",
        classifier: "not_configured",
        model_identifier: null,
        segmentation_rule_version: "claim-segmentation-v1",
        evidence: [
          {
            id: "77777777-7777-4777-8777-777777777777",
            source_type: "citation",
            source_id: "88888888-8888-4888-8888-888888888888",
            source_reference: "citation:northstar",
            url: "https://northstar.example/product",
            excerpt: "Northstar AI provides broad citation monitoring.",
            relevance_score: 0.84,
            retrieval_rule_version: "evidence-retrieval-v1",
          },
        ],
      },
    ];

    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/geolens/projects")) return response([project]);
      if (url.endsWith("/api/geolens/providers")) return response(providers);
      if (url.endsWith("/api/geolens/analyses") && init?.method === "POST") {
        return response(analysis, 201);
      }
      if (url.endsWith("/citations")) return response([]);
      if (url.endsWith("/entities")) return response([]);
      if (url.endsWith("/scores")) return response([]);
      if (url.endsWith("/claims")) return response(claims);
      return response({ detail: `Unexpected request: ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Dashboard />);

    expect(await screen.findByRole("heading", { name: "Acme Cloud overview" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Run analysis" }));

    expect(
      await screen.findByText("Analysis completed and evidence is ready"),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Ranked GEO recommendations" })).toBeVisible();
    expect(
      screen.getByText(/Northstar AI appears while Acme Cloud is absent/),
    ).toBeVisible();
    expect(screen.getAllByText("Provider evidence")[0]).toBeVisible();
    expect(screen.getAllByText("Expected metric")[0]).toBeVisible();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/geolens/analyses",
        expect.objectContaining({
          method: "POST",
        }),
      );
    });
  });
});
