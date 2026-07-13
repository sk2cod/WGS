import type { BrandKit, Mood, ResolvedTokens } from "./types";

/**
 * Resolves a mood against a BrandKit into the flat token shape the render
 * contract (Section 8) expects. The backend performs this same resolution
 * before calling /api/render — the frontend never picks a mood on its own,
 * it only ever renders whatever palette it's handed.
 */
export function resolveTokens(brandKit: BrandKit, mood: Mood): ResolvedTokens {
  const palette = brandKit.mood_palettes[mood];
  return {
    primary: palette.primary,
    secondary: palette.secondary,
    accent: palette.accent,
    text_color: brandKit.text_color,
    background_color: brandKit.background_color,
    font_heading: brandKit.font_heading,
    font_script: brandKit.font_script,
    font_body: brandKit.font_body,
  };
}

/** CSS custom properties for the (browser-only) chrome around a rendered slide — never used inside the Satori-rendered templates themselves, since Satori doesn't resolve var(). */
export function tokensToCssVars(tokens: ResolvedTokens): React.CSSProperties {
  return {
    "--primary": tokens.primary,
    "--secondary": tokens.secondary,
    "--accent": tokens.accent,
    "--text-color": tokens.text_color,
    "--background-color": tokens.background_color,
  } as React.CSSProperties;
}
