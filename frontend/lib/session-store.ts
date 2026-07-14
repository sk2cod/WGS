import type { GenerateResponse } from "./api-types";

/** No backend persistence exists yet (Supabase lands in Phase 6) — the in-progress
 * post is round-tripped through the client across Generate -> Editor -> Export via
 * sessionStorage, the same "client holds the brief" pattern the API itself uses for
 * /generate/regenerate-slide and /generate/reshuffle-image.
 *
 * The hero image (a multi-MB base64 string) is kept out of sessionStorage and held
 * in memory instead — writing it there reliably threw a real, uncaught
 * QuotaExceededError on mobile Safari, surfaced to the user as a misleading
 * "The quota has been exceeded" error on Generate (nothing to do with the Anthropic/
 * OpenAI request, which had already succeeded by that point). Tradeoff: the hero
 * image is lost on a hard page reload mid-flow (module state doesn't survive that),
 * where the rest of the post still would; that's an acceptable, rare degradation
 * next to the previous failure mode, which blocked every single carousel generate. */
const KEY = "wgs-current-post";

let cachedHeroImage: string | null = null;

export function saveCurrentPost(data: GenerateResponse): void {
  if (typeof window === "undefined") return;
  cachedHeroImage = data.hero_image_base64;
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ ...data, hero_image_base64: null }));
  } catch {
    // Text-only payload still exceeded quota (e.g. Safari Private Browsing, which
    // reports a ~0 quota) — the in-memory state above is enough to keep the current
    // tab's flow working; only a hard reload would lose the post entirely now.
  }
}

export function loadCurrentPost(): GenerateResponse | null {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(KEY);
  if (!raw) return null;
  try {
    const data = JSON.parse(raw) as GenerateResponse;
    return { ...data, hero_image_base64: cachedHeroImage };
  } catch {
    return null;
  }
}

export function clearCurrentPost(): void {
  if (typeof window === "undefined") return;
  cachedHeroImage = null;
  sessionStorage.removeItem(KEY);
}
