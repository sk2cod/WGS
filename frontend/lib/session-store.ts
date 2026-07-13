import type { GenerateResponse } from "./api-types";

/** No backend persistence exists yet (Supabase lands in Phase 6) — the in-progress
 * post is round-tripped through the client across Generate -> Editor -> Export via
 * sessionStorage, the same "client holds the brief" pattern the API itself uses for
 * /generate/regenerate-slide and /generate/reshuffle-image. */
const KEY = "wgs-current-post";

export function saveCurrentPost(data: GenerateResponse): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(KEY, JSON.stringify(data));
}

export function loadCurrentPost(): GenerateResponse | null {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as GenerateResponse;
  } catch {
    return null;
  }
}

export function clearCurrentPost(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(KEY);
}
