const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");
const PLACEHOLDER_MARKERS = [
  "your_current",
  "replace-me",
  "replace_me",
  "changeme",
  "change_me",
  "placeholder",
  "example",
];

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

function configuredApiKey(): string {
  const key = (process.env.NEXT_PUBLIC_API_KEY ?? "").trim();
  const lowered = key.toLowerCase();
  if (
    !/^frk_[A-Za-z0-9_-]{32,}$/.test(key) ||
    PLACEHOLDER_MARKERS.some((marker) => lowered.includes(marker))
  ) {
    throw new ApiError("Demo API key is not configured", 0);
  }
  return key;
}

function isErrorPayload(value: unknown): value is { detail: string } {
  return (
    typeof value === "object" &&
    value !== null &&
    "detail" in value &&
    typeof value.detail === "string"
  );
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const apiKey = configuredApiKey();
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...init,
      headers: {
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        Authorization: `Bearer ${apiKey}`,
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      "The API is unreachable. Confirm the backend is running and try again.",
      0,
    );
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = isErrorPayload(payload) ? payload.detail : "Request failed";
    throw new ApiError(humanizeApiError(response.status, detail), response.status);
  }
  return payload as T;
}

export async function apiBlobRequest(
  path: string,
  init?: RequestInit,
): Promise<Blob> {
  const apiKey = configuredApiKey();
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...init,
      headers: {
        Authorization: `Bearer ${apiKey}`,
        ...init?.headers,
      },
    });
  } catch (reason) {
    if (reason instanceof DOMException && reason.name === "AbortError") throw reason;
    throw new ApiError(
      "The API is unreachable. Confirm the backend is running and try again.",
      0,
    );
  }
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail = isErrorPayload(payload) ? payload.detail : "Image request failed";
    throw new ApiError(humanizeApiError(response.status, detail), response.status);
  }
  return response.blob();
}

function humanizeApiError(status: number, detail: string): string {
  if (status === 409 && detail.toLowerCase().includes("embedding")) {
    return "Generate the post embedding before searching for images.";
  }
  if (status === 404 && detail.toLowerCase().includes("evaluation")) {
    return "No evaluation run exists yet. Run the deterministic evaluation, then try again.";
  }
  if (status === 404 && detail.toLowerCase().includes("recommendation")) {
    return "This recommendation could not be found. Check the review link and try again.";
  }
  if (status === 404) return detail || "The requested record was not found.";
  if (status === 422) return "Please check the highlighted input and try again.";
  if ([500, 503, 504].includes(status)) {
    return "The service could not complete this request. Please try again shortly.";
  }
  return detail;
}

export function assertArray(value: unknown, label: string): asserts value is unknown[] {
  if (!Array.isArray(value)) throw new ApiError(`Invalid ${label} response`, 502);
}
