import { NextRequest, NextResponse } from "next/server";

const ALLOWED_PATHS = [
  /^projects$/,
  /^projects\/[0-9a-f-]{36}$/i,
  /^providers$/,
  /^analyses$/,
  /^analyses\/[0-9a-f-]{36}\/(citations|entities|scores|claims)$/i,
  /^sites\/[0-9a-f-]{36}\/crawls$/i,
  /^crawls\/[0-9a-f-]{36}$/i,
];

const GET_ONLY_ALLOWED_PATHS = [/^sites\/[0-9a-f-]{36}\/crawls\/latest$/i];

function isAllowed(path: string, method: string): boolean {
  return (
    ALLOWED_PATHS.some((pattern) => pattern.test(path)) ||
    (method === "GET" && GET_ONLY_ALLOWED_PATHS.some((pattern) => pattern.test(path)))
  );
}

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path: segments } = await context.params;
  const path = segments.join("/");
  if (!isAllowed(path, request.method)) {
    return NextResponse.json({ detail: "Unknown API route" }, { status: 404 });
  }

  const baseUrl = process.env.GEOLENS_API_URL ?? "http://localhost:8000";
  const upstream = new URL(path, `${baseUrl.replace(/\/$/, "")}/`);
  upstream.search = request.nextUrl.search;

  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.text();
  try {
    const response = await fetch(upstream, {
      method: request.method,
      headers: {
        Accept: "application/json",
        ...(body ? { "Content-Type": request.headers.get("content-type") ?? "application/json" } : {}),
      },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(120_000),
    });
    return new NextResponse(response.body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "The GeoLens API is currently unavailable." },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
