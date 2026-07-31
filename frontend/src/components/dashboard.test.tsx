import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  AnalysisClaimResponse,
  AnalysisStartResponse,
  CrawlJobResponse,
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

const publicProject: ProjectResponse = {
  ...project,
  id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  name: "Orbit Labs",
  aliases: ["Orbit"],
  site: {
    id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    project_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    url: "https://orbitlabs.com/",
    created_at: "2026-07-30T08:00:00Z",
    updated_at: "2026-07-30T08:00:00Z",
  },
};

const secondProject: ProjectResponse = {
  ...project,
  id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  name: "Summit Labs",
  aliases: ["Summit"],
  site: {
    id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    project_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    url: "https://summitlabs.com/",
    created_at: "2026-07-30T08:00:00Z",
    updated_at: "2026-07-30T08:00:00Z",
  },
};

function crawlJob(
  status: CrawlJobResponse["status"],
  overrides: Partial<CrawlJobResponse> = {},
): CrawlJobResponse {
  return {
    id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    site_id: publicProject.site!.id,
    status,
    started_at: status === "pending" ? null : "2026-07-30T08:01:00Z",
    completed_at: ["succeeded", "failed"].includes(status)
      ? "2026-07-30T08:01:05Z"
      : null,
    error_message: null,
    celery_task_id: "crawl-task-1",
    page_count: status === "succeeded" ? 7 : 0,
    error_count: status === "succeeded" ? 2 : 0,
    created_at: "2026-07-30T08:00:59Z",
    updated_at: "2026-07-30T08:01:05Z",
    ...overrides,
  };
}

function completedAnalysis(id = "99999999-9999-4999-8999-999999999999"): AnalysisStartResponse {
  return {
    analysis_id: id,
    project_id: project.id,
    crawl_job_id: null,
    status: "succeeded",
    started_at: "2026-07-30T09:00:00Z",
    completed_at: "2026-07-30T09:00:01Z",
    error_message: null,
    celery_task_id: "analysis-task-1",
    provider_configurations: [{ name: "mock", model_identifier: "mock-v1" }],
    prompts: [],
    claim_classifier_configuration: null,
    persisted: false,
    results: [],
    created_at: "2026-07-30T09:00:00Z",
    updated_at: "2026-07-30T09:00:01Z",
  };
}

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
  vi.useRealTimers();
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
    const analysis: AnalysisStartResponse = {
      analysis_id: "44444444-4444-4444-8444-444444444444",
      project_id: project.id,
      crawl_job_id: null,
      status: "succeeded",
      started_at: "2026-07-30T09:00:00.000Z",
      completed_at: "2026-07-30T09:00:00.025Z",
      error_message: null,
      celery_task_id: "analysis-task-1",
      provider_configurations: [{ name: "mock", model_identifier: "mock-v1" }],
      prompts: [],
      claim_classifier_configuration: null,
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
      created_at: "2026-07-30T09:00:00.000Z",
      updated_at: "2026-07-30T09:00:00.025Z",
    };
    const queuedAnalysis: AnalysisStartResponse = {
      ...analysis,
      status: "pending",
      started_at: null,
      completed_at: null,
      results: [],
      updated_at: analysis.created_at,
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
        response_prompt: "Compare Acme Cloud with Northstar AI for citation monitoring.",
        response_provider: "mock",
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

    let analysisStatusReads = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/geolens/projects")) return response([project]);
      if (url.endsWith("/api/geolens/providers")) return response(providers);
      if (url.endsWith("/api/geolens/analyses") && init?.method === "POST") {
        return response(queuedAnalysis, 202);
      }
      if (url.endsWith(`/api/geolens/analyses/${analysis.analysis_id}`)) {
        analysisStatusReads += 1;
        return response(
          analysisStatusReads === 1
            ? { ...queuedAnalysis, status: "running", started_at: analysis.started_at }
            : analysis,
        );
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
    expect(
      screen.getByText(/The seeded demo uses a non-routable example domain/),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Crawl website" })).toBeDisabled();
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole("button", { name: "Run analysis" }));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByRole("button", { name: "Analyzing…" })).toBeDisabled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(analysisStatusReads).toBe(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(analysisStatusReads).toBe(2);

    expect(
      screen.getByText("Analysis completed and evidence is ready"),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Ranked GEO recommendations" })).toBeVisible();
    expect(
      screen.getByText(/Northstar AI appears while Acme Cloud is absent/),
    ).toBeVisible();
    expect(screen.getAllByText("Provider evidence")[0]).toBeVisible();
    expect(screen.getAllByText("Expected metric")[0]).toBeVisible();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/geolens/analyses",
      expect.objectContaining({
        method: "POST",
      }),
    );

    const analysisCall = fetchMock.mock.calls.find(([input, init]) =>
      String(input).endsWith("/api/geolens/analyses") && init?.method === "POST",
    );
    const analysisBody = JSON.parse(String(analysisCall?.[1]?.body)) as Record<string, unknown>;
    expect(analysisBody.providers).toEqual(["mock"]);
    expect(analysisBody).not.toHaveProperty("crawl_job_id");
    expect(screen.getByText("Analysis ran without website crawl evidence")).toBeVisible();
    expect(
      fetchMock.mock.calls.some(([input]) => String(input).includes("/crawls")),
    ).toBe(false);
  });

  it("uses the active site ID, polls pending and running states, stops at success, and attaches the crawl", async () => {
    let statusReads = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/geolens/projects")) return response([publicProject]);
      if (url.endsWith("/api/geolens/providers")) return response(providers);
      if (url.endsWith(`/sites/${publicProject.site!.id}/crawls/latest`)) {
        return response(null);
      }
      if (
        url.endsWith(`/api/geolens/sites/${publicProject.site!.id}/crawls`) &&
        init?.method === "POST"
      ) {
        return response(crawlJob("pending"), 202);
      }
      if (url.endsWith("/api/geolens/crawls/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")) {
        statusReads += 1;
        return response(statusReads === 1 ? crawlJob("running") : crawlJob("succeeded"));
      }
      if (url.endsWith("/api/geolens/analyses") && init?.method === "POST") {
        return response(completedAnalysis(), 201);
      }
      return response({ detail: `Unexpected request: ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Dashboard />);
    expect(await screen.findByRole("heading", { name: "Orbit Labs overview" })).toBeVisible();
    expect(await screen.findByRole("button", { name: "Crawl website" })).toBeEnabled();

    vi.useFakeTimers();
    fireEvent.click(screen.getByRole("button", { name: "Crawl website" }));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByText("Crawl queued")).toBeVisible();
    expect(screen.getByRole("button", { name: "Crawl in progress" })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/geolens/sites/${publicProject.site!.id}/crawls`,
      expect.objectContaining({ method: "POST" }),
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(screen.getByText("Crawling website")).toBeVisible();
    expect(statusReads).toBe(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(screen.getByText("Website crawl succeeded")).toBeVisible();
    expect(screen.getByText("Pages crawled").parentElement).toHaveTextContent("7");
    expect(screen.getByText("Errors").parentElement).toHaveTextContent("2");
    expect(statusReads).toBe(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(statusReads).toBe(2);

    fireEvent.click(screen.getByRole("button", { name: "Run analysis" }));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const analysisCall = fetchMock.mock.calls.find(([input, init]) =>
      String(input).endsWith("/api/geolens/analyses") && init?.method === "POST",
    );
    const analysisBody = JSON.parse(String(analysisCall?.[1]?.body)) as Record<string, unknown>;
    expect(analysisBody.crawl_job_id).toBe("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee");
    expect(screen.getByText(/Website evidence attached.+7 pages/)).toBeVisible();
  });

  it("shows a failed crawl error and omits the failed crawl from analysis", async () => {
    const failed = crawlJob("failed", {
      error_message: "Robots policy prevented the crawl.",
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/geolens/projects")) return response([publicProject]);
      if (url.endsWith("/api/geolens/providers")) return response(providers);
      if (url.endsWith(`/sites/${publicProject.site!.id}/crawls/latest`)) {
        return response(null);
      }
      if (url.endsWith("/crawls") && init?.method === "POST") return response(failed, 202);
      if (url.endsWith("/api/geolens/analyses") && init?.method === "POST") {
        return response(completedAnalysis(), 201);
      }
      return response({ detail: `Unexpected request: ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<Dashboard />);
    expect(await screen.findByRole("heading", { name: "Orbit Labs overview" })).toBeVisible();
    await user.click(await screen.findByRole("button", { name: "Crawl website" }));

    expect(await screen.findByText("Website crawl failed")).toBeVisible();
    expect(screen.getByText("Robots policy prevented the crawl.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Run analysis" }));

    await waitFor(() => {
      expect(screen.getByText("Analysis ran without website crawl evidence")).toBeVisible();
    });
    const analysisCall = fetchMock.mock.calls.find(([input, init]) =>
      String(input).endsWith("/api/geolens/analyses") && init?.method === "POST",
    );
    const analysisBody = JSON.parse(String(analysisCall?.[1]?.body)) as Record<string, unknown>;
    expect(analysisBody).not.toHaveProperty("crawl_job_id");
  });

  it("clears crawl evidence when switching away and recovers it when switching back", async () => {
    let publicSiteHasCrawl = false;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/geolens/projects")) {
        return response([publicProject, secondProject]);
      }
      if (url.endsWith("/api/geolens/providers")) return response(providers);
      if (url.endsWith(`/sites/${publicProject.site!.id}/crawls/latest`)) {
        return response(publicSiteHasCrawl ? crawlJob("succeeded") : null);
      }
      if (url.endsWith(`/sites/${secondProject.site!.id}/crawls/latest`)) {
        return response(null);
      }
      if (url.endsWith("/crawls") && init?.method === "POST") {
        publicSiteHasCrawl = true;
        return response(crawlJob("succeeded"), 202);
      }
      if (url.endsWith("/api/geolens/analyses") && init?.method === "POST") {
        return response(completedAnalysis(), 201);
      }
      return response({ detail: `Unexpected request: ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<Dashboard />);
    expect(await screen.findByRole("heading", { name: "Orbit Labs overview" })).toBeVisible();
    await user.click(await screen.findByRole("button", { name: "Crawl website" }));
    expect(await screen.findByText("Website crawl succeeded")).toBeVisible();

    await user.selectOptions(screen.getByLabelText("Active project"), secondProject.id);
    expect(screen.getByRole("heading", { name: "Summit Labs overview" })).toBeVisible();
    expect(screen.queryByText("Website crawl succeeded")).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Crawl website" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Run analysis" }));
    await waitFor(() => {
      expect(screen.getByText("Analysis ran without website crawl evidence")).toBeVisible();
    });
    const analysisCall = fetchMock.mock.calls.find(([input, init]) =>
      String(input).endsWith("/api/geolens/analyses") && init?.method === "POST",
    );
    const analysisBody = JSON.parse(String(analysisCall?.[1]?.body)) as Record<string, unknown>;
    expect(analysisBody.project_id).toBe(secondProject.id);
    expect(analysisBody).not.toHaveProperty("crawl_job_id");

    await user.selectOptions(screen.getByLabelText("Active project"), publicProject.id);
    expect(screen.getByRole("heading", { name: "Orbit Labs overview" })).toBeVisible();
    expect(await screen.findByText("Website crawl succeeded")).toBeVisible();
    expect(screen.getByText("Pages crawled").parentElement).toHaveTextContent("7");
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/geolens/sites/${publicProject.site!.id}/crawls/latest`,
      expect.anything(),
    );
  });

  it("recovers a persisted successful crawl on dashboard load", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/geolens/projects")) return response([publicProject]);
      if (url.endsWith("/api/geolens/providers")) return response(providers);
      if (url.endsWith(`/sites/${publicProject.site!.id}/crawls/latest`)) {
        return response(crawlJob("succeeded"));
      }
      return response({ detail: `Unexpected request: ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Dashboard />);

    expect(await screen.findByText("Website crawl succeeded")).toBeVisible();
    expect(screen.getByText("Pages crawled").parentElement).toHaveTextContent("7");
    expect(screen.getByText("Errors").parentElement).toHaveTextContent("2");
  });

  it("recovers a persisted failed crawl and its counts on dashboard load", async () => {
    const failed = crawlJob("failed", {
      error_message: "The website timed out.",
      page_count: 3,
      error_count: 4,
    });
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/geolens/projects")) return response([publicProject]);
      if (url.endsWith("/api/geolens/providers")) return response(providers);
      if (url.endsWith(`/sites/${publicProject.site!.id}/crawls/latest`)) {
        return response(failed);
      }
      return response({ detail: `Unexpected request: ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Dashboard />);

    expect(await screen.findByText("Website crawl failed")).toBeVisible();
    expect(screen.getByText("The website timed out.")).toBeVisible();
    expect(screen.getByText("Pages crawled").parentElement).toHaveTextContent("3");
    expect(screen.getByText("Errors").parentElement).toHaveTextContent("4");
  });

  it("shows an empty crawl state when the active project has no crawl", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/geolens/projects")) return response([publicProject]);
      if (url.endsWith("/api/geolens/providers")) return response(providers);
      if (url.endsWith(`/sites/${publicProject.site!.id}/crawls/latest`)) {
        return response(null);
      }
      return response({ detail: `Unexpected request: ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Dashboard />);

    expect(await screen.findByRole("button", { name: "Crawl website" })).toBeEnabled();
    expect(screen.getByText("Use website text as optional evidence")).toBeVisible();
    expect(screen.queryByText("Website crawl succeeded")).not.toBeInTheDocument();
  });

  it.each(["pending", "running"] as const)(
    "continues polling after recovering a %s crawl",
    async (recoveredStatus) => {
      let resolveLatest!: (response: Response) => void;
      const latestResponse = new Promise<Response>((resolve) => {
        resolveLatest = resolve;
      });
      let statusReads = 0;
      const fetchMock = vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/geolens/projects")) return response([publicProject]);
        if (url.endsWith("/api/geolens/providers")) return response(providers);
        if (url.endsWith(`/sites/${publicProject.site!.id}/crawls/latest`)) {
          return latestResponse;
        }
        if (url.endsWith("/api/geolens/crawls/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")) {
          statusReads += 1;
          return response(crawlJob("succeeded"));
        }
        return response({ detail: `Unexpected request: ${url}` }, 500);
      });
      vi.stubGlobal("fetch", fetchMock);

      render(<Dashboard />);
      expect(await screen.findByRole("heading", { name: "Orbit Labs overview" })).toBeVisible();
      vi.useFakeTimers();
      await act(async () => {
        resolveLatest(await response(crawlJob(recoveredStatus)));
        await Promise.resolve();
      });

      expect(
        screen.getByText(recoveredStatus === "pending" ? "Crawl queued" : "Crawling website"),
      ).toBeVisible();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2_000);
      });

      expect(screen.getByText("Website crawl succeeded")).toBeVisible();
      expect(statusReads).toBe(1);
    },
  );

  it("cancels scheduled crawl polling when the dashboard unmounts", async () => {
    let statusReads = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/geolens/projects")) return response([publicProject]);
      if (url.endsWith("/api/geolens/providers")) return response(providers);
      if (url.endsWith(`/sites/${publicProject.site!.id}/crawls/latest`)) {
        return response(null);
      }
      if (url.endsWith("/crawls") && init?.method === "POST") {
        return response(crawlJob("pending"), 202);
      }
      if (url.includes("/api/geolens/crawls/")) {
        statusReads += 1;
        return response(crawlJob("running"));
      }
      return response({ detail: `Unexpected request: ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    const rendered = render(<Dashboard />);
    expect(await screen.findByRole("heading", { name: "Orbit Labs overview" })).toBeVisible();
    expect(await screen.findByRole("button", { name: "Crawl website" })).toBeEnabled();
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole("button", { name: "Crawl website" }));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("Crawl queued")).toBeVisible();

    rendered.unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    expect(statusReads).toBe(0);
  });

  it("preserves polling errors and lets the user retry the status request", async () => {
    let statusReads = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/geolens/projects")) return response([publicProject]);
      if (url.endsWith("/api/geolens/providers")) return response(providers);
      if (url.endsWith(`/sites/${publicProject.site!.id}/crawls/latest`)) {
        return response(null);
      }
      if (url.endsWith("/crawls") && init?.method === "POST") {
        return response(crawlJob("pending"), 202);
      }
      if (url.includes("/api/geolens/crawls/")) {
        statusReads += 1;
        return statusReads === 1
          ? response({ detail: "Temporary status outage" }, 503)
          : response(crawlJob("succeeded"));
      }
      return response({ detail: `Unexpected request: ${url}` }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Dashboard />);
    expect(await screen.findByRole("heading", { name: "Orbit Labs overview" })).toBeVisible();
    expect(await screen.findByRole("button", { name: "Crawl website" })).toBeEnabled();
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole("button", { name: "Crawl website" }));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(screen.getByText("Crawl status check paused")).toBeVisible();
    expect(screen.getByText("Temporary status outage")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Retry status check" }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(screen.getByText("Website crawl succeeded")).toBeVisible();
    expect(statusReads).toBe(2);
  });
});
