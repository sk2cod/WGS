import type { MastheadInfo, ResolvedTokens } from "@/lib/types";

interface MastheadProps {
  masthead: MastheadInfo;
  tokens: ResolvedTokens;
  /** Overrides tokens.text_color — CarouselClosing sits on a dark `primary`
   * background and needs the masthead in `secondary` instead. */
  color?: string;
}

/**
 * Shared running header used at the top of all five templates:
 * {masthead_short} — thin rule — {category} NO. {n}
 * Small-caps look is emulated via uppercase + letter-spacing since Satori's
 * CSS subset doesn't support font-variant: small-caps.
 */
export default function Masthead({ masthead, tokens, color }: MastheadProps) {
  const ink = color ?? tokens.text_color;
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "row",
        alignItems: "center",
        gap: 14,
        opacity: 0.65,
      }}
    >
      <span
        style={{
          fontFamily: tokens.font_body,
          fontSize: 22,
          fontWeight: 600,
          letterSpacing: 3,
          textTransform: "uppercase",
          color: ink,
        }}
      >
        {masthead.masthead_short}
      </span>
      <div
        style={{
          width: 32,
          height: 1,
          backgroundColor: ink,
        }}
      />
      <span
        style={{
          fontFamily: tokens.font_body,
          fontSize: 22,
          fontWeight: 600,
          letterSpacing: 3,
          textTransform: "uppercase",
          color: ink,
        }}
      >
        {masthead.category} NO. {masthead.number}
      </span>
    </div>
  );
}
