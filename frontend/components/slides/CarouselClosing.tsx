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
 *
 * logbook #39, round 8: only takeaway renders now. signature/cta/handle were
 * removed from display (signature — display-only, #32's pattern, the field
 * still flows from the backend unchanged) or relocated to ConversationSlide
 * (cta/handle — the true last slide as of round 7, where they belong).
 */
export default function CarouselClosing({ masthead, tokens, takeaway }: CarouselClosingProps) {
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
      </div>
    </SlideFrame>
  );
}
