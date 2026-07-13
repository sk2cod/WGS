import type { CarouselClosingContent, MastheadInfo, ResolvedTokens } from "@/lib/types";
import Masthead from "./Masthead";
import SlideFrame from "./SlideFrame";

interface CarouselClosingProps extends CarouselClosingContent {
  masthead: MastheadInfo;
  tokens: ResolvedTokens;
}

/**
 * Background = mood's primary, text = mood's secondary. Masthead stays pinned
 * top in normal flow; everything else lives in its own flex:1 wrapper that
 * centers *within itself* — justify-content must never land on the whole
 * slide here, or it drags the masthead down with it.
 */
export default function CarouselClosing({
  masthead,
  tokens,
  takeaway,
  signature,
  cta,
  handle,
}: CarouselClosingProps) {
  const onPrimary = tokens.secondary;

  return (
    <SlideFrame backgroundColor={tokens.primary}>
      <Masthead masthead={masthead} tokens={tokens} color={onPrimary} />

      <div
        style={{
          display: "flex",
          flex: 1,
          flexDirection: "column",
          justifyContent: "center",
          gap: 28,
        }}
      >
        <span
          style={{
            fontFamily: tokens.font_body,
            fontWeight: 700,
            fontSize: 48,
            lineHeight: 1.3,
            color: onPrimary,
          }}
        >
          {takeaway}
        </span>
        <span
          style={{
            fontFamily: tokens.font_script,
            fontSize: 56,
            color: onPrimary,
          }}
        >
          {signature}
        </span>
        <span
          style={{
            fontFamily: tokens.font_body,
            fontWeight: 400,
            fontSize: 30,
            lineHeight: 1.4,
            color: onPrimary,
          }}
        >
          {cta}
        </span>
        <span
          style={{
            fontFamily: tokens.font_body,
            fontWeight: 600,
            fontSize: 18,
            letterSpacing: 3,
            textTransform: "uppercase",
            color: onPrimary,
            opacity: 0.65,
          }}
        >
          {handle}
        </span>
      </div>
    </SlideFrame>
  );
}
