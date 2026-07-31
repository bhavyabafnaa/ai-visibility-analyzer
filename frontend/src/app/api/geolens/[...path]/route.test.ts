import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { GET, POST } from "./route";

const siteId = "11111111-1111-4111-8111-111111111111";

function context(...path: string[]) {
  return { params: Promise.resolve({ path }) };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("GeoLens API proxy allowlist", () => {
  it("allows GET sites/{uuid}/crawls/latest", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "latest-crawl" }), {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(
      new NextRequest(
        `http://localhost/api/geolens/sites/${siteId}/crawls/latest?include=summary`,
      ),
      context("sites", siteId, "crawls", "latest"),
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ id: "latest-crawl" });
    expect(fetchMock).toHaveBeenCalledOnce();
    const [upstream, init] = fetchMock.mock.calls[0] as [URL, RequestInit];
    expect(upstream.toString()).toBe(
      `http://localhost:8000/sites/${siteId}/crawls/latest?include=summary`,
    );
    expect(init.method).toBe("GET");
  });

  it("does not allow POST sites/{uuid}/crawls/latest", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new NextRequest(
        `http://localhost/api/geolens/sites/${siteId}/crawls/latest`,
        { method: "POST" },
      ),
      context("sites", siteId, "crawls", "latest"),
    );

    expect(response.status).toBe(404);
    expect(await response.json()).toEqual({ detail: "Unknown API route" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps an existing POST route allowed", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "new-crawl" }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new NextRequest(`http://localhost/api/geolens/sites/${siteId}/crawls`, {
        method: "POST",
        body: JSON.stringify({ max_pages: 10 }),
        headers: { "Content-Type": "application/json" },
      }),
      context("sites", siteId, "crawls"),
    );

    expect(response.status).toBe(202);
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
