import type { KnowledgeMap, Topic, TopicSummary, Trail, Viewport } from "./types";

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, credentials: "same-origin" });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(payload.message ?? payload.detail?.message ?? "Request failed");
  }
  return response.json() as Promise<T>;
}

export function getMaps(signal?: AbortSignal): Promise<KnowledgeMap[]> {
  return request("/api/v1/maps", signal);
}

export function getMap(id: string, signal?: AbortSignal): Promise<KnowledgeMap> {
  return request(`/api/v1/maps/${id}`, signal);
}

export function getViewport(
  mapId: string,
  bounds: { min_x: number; min_y: number; max_x: number; max_y: number },
  zoom: number,
  signal?: AbortSignal,
): Promise<Viewport> {
  const query = new URLSearchParams({
    min_x: String(bounds.min_x),
    min_y: String(bounds.min_y),
    max_x: String(bounds.max_x),
    max_y: String(bounds.max_y),
    zoom: String(zoom),
  });
  return request(`/api/v1/maps/${mapId}/viewport?${query}`, signal);
}

export function getTopic(id: string, signal?: AbortSignal): Promise<Topic> {
  return request(`/api/v1/topics/${id}`, signal);
}

export function searchTopics(query: string, signal?: AbortSignal): Promise<{ items: TopicSummary[] }> {
  return request(`/api/v1/topics?q=${encodeURIComponent(query)}&limit=100`, signal);
}

export function getTrails(signal?: AbortSignal): Promise<{ id: string; title: string; summary: string }[]> {
  return request("/api/v1/trails", signal);
}

export function getTrail(id: string, signal?: AbortSignal): Promise<Trail> {
  return request(`/api/v1/trails/${id}`, signal);
}

export type Identity =
  | { authenticated: false }
  | { authenticated: true; id: string; display_name: string; role: string; csrf_token: string | null };

export function getIdentity(signal?: AbortSignal): Promise<Identity> {
  return request("/api/v1/auth/me", signal);
}

export async function logout(csrfToken: string): Promise<void> {
  const response = await fetch("/api/v1/auth/logout", {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-CSRF-Token": csrfToken },
  });
  if (!response.ok) throw new Error("Sign out failed");
}
