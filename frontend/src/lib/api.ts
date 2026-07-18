import type { ZodType } from "zod";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(
  path: string,
  schema: ZodType<T>,
  init: RequestInit = {},
  accessToken?: string | null,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const response = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string | Array<{ msg?: string }> };
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((item) => item.msg).filter(Boolean).join(", ") || message;
    } catch {
      // Preserve the status-based message when the server did not return JSON.
    }
    throw new ApiError(response.status, message);
  }
  return schema.parse(await response.json());
}

export function createIdempotencyKey(scope: string): string {
  return `${scope}-${crypto.randomUUID()}`;
}

export function storeIncidentToken(incidentId: string, token?: string | null): void {
  if (typeof window !== "undefined" && token) localStorage.setItem(`adris:incident:${incidentId}`, token);
}

export function getIncidentToken(incidentId: string): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(`adris:incident:${incidentId}`);
}

export function incidentHeaders(incidentId: string, extras?: HeadersInit): Headers {
  const headers = new Headers(extras);
  const token = getIncidentToken(incidentId);
  if (token) headers.set("X-Incident-Token", token);
  return headers;
}
