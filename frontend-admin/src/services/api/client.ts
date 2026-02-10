import type { ApiErrorPayload } from "@/types/api";

export class ApiRequestError extends Error {
  readonly status: number;
  readonly payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.payload = payload;
  }
}

function sanitizeBaseUrl(rawBaseUrl: string | undefined): string {
  if (!rawBaseUrl) {
    throw new Error("Missing NEXT_PUBLIC_API_URL");
  }

  return rawBaseUrl.replace(/\/+$/, "");
}

function getPayloadMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const typedPayload = payload as ApiErrorPayload;
  if (typeof typedPayload.message === "string") {
    return typedPayload.message;
  }

  if (typeof typedPayload.detail === "string") {
    return typedPayload.detail;
  }

  return null;
}

async function parseResponsePayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }

  const text = await response.text();
  return text.length > 0 ? { message: text } : null;
}

function buildRequestHeaders(init?: RequestInit): Headers {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  return headers;
}

export function getApiBaseUrl(): string {
  return sanitizeBaseUrl(process.env.NEXT_PUBLIC_API_URL);
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: buildRequestHeaders(init),
  });

  const payload = await parseResponsePayload(response);

  if (!response.ok) {
    const message = getPayloadMessage(payload) ?? `Request failed with status ${response.status}`;
    throw new ApiRequestError(message, response.status, payload);
  }

  return payload as T;
}
