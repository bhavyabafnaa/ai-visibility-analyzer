export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiRequest<T>(
  path: string,
  init?: Omit<RequestInit, "body"> & { body?: unknown },
): Promise<T> {
  const response = await fetch(`/api/geolens${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body === undefined ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
    body: init?.body === undefined ? undefined : JSON.stringify(init.body),
  });

  const payload = (await response.json().catch(() => null)) as
    | { detail?: string; error?: string }
    | null;
  if (!response.ok) {
    throw new ApiError(
      payload?.detail ?? payload?.error ?? `Request failed with status ${response.status}`,
      response.status,
    );
  }
  return payload as T;
}
