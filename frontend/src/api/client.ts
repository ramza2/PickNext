const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "/api/v1"
).replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function joinUrl(base: string, path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalizedPath}`;
}

function messageFromDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return null;
      })
      .filter(Boolean);
    if (parts.length) return parts.join("; ");
  }
  if (detail && typeof detail === "object") {
    const record = detail as { message?: unknown; code?: unknown };
    if (typeof record.message === "string" && record.message.trim()) {
      return record.message;
    }
    if (typeof record.code === "string" && record.code.trim()) {
      return record.code;
    }
  }
  return fallback;
}

export async function apiRequest<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const url = joinUrl(API_BASE_URL, path);
  const headers = new Headers(options?.headers);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  if (options?.body != null && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (err) {
    const message =
      err instanceof Error && err.name === "AbortError"
        ? "Request aborted"
        : "Network error";
    throw new ApiError(0, message, err);
  }

  if (response.ok) {
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }

  let detail: unknown;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      const body = await response.json();
      detail = body?.detail ?? body;
    } catch {
      detail = undefined;
    }
  } else {
    try {
      detail = await response.text();
    } catch {
      detail = undefined;
    }
  }

  throw new ApiError(
    response.status,
    messageFromDetail(detail, `Request failed (${response.status})`),
    detail,
  );
}
