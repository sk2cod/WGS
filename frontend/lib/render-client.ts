import type { ApiSlide } from "./api-types";
import type { MastheadInfo, ResolvedTokens, TemplateId } from "./types";

/** Calls the Satori render route (Section 8) for one slide and returns a PNG blob. */
export async function renderSlideToBlob(
  slide: ApiSlide,
  masthead: MastheadInfo,
  tokens: ResolvedTokens,
  heroImageUrl?: string | null,
): Promise<Blob> {
  const res = await fetch("/api/render", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      template_id: slide.template_id as TemplateId,
      slides: [slide],
      masthead,
      tokens,
      hero_image_url: slide.template_id === "carousel_cover" ? heroImageUrl : null,
    }),
  });
  if (!res.ok) {
    throw new Error(`render failed for ${slide.template_id}: ${res.status}`);
  }
  return res.blob();
}
