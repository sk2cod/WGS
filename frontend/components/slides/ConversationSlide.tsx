import type { CarouselConversationContent, MastheadInfo, ResolvedTokens } from "@/lib/types";
import Masthead from "./Masthead";
import SlideFrame from "./SlideFrame";

interface ConversationSlideProps extends CarouselConversationContent {
  masthead: MastheadInfo;
  tokens: ResolvedTokens;
}

/**
 * The real CTA/question slide (logbook #39, round 7) — the first structural,
 * not prompt-only, change in the v1 line of work. Appended after
 * CarouselClosing for every carousel post — the true last slide. label,
 * invite, cta, and handle are all fixed brand copy; only question is
 * model-written.
 *
 * Same masthead-pinned-top / flex:1-centered-wrapper layout convention as
 * CarouselClosing, on the light background instead of the mood's primary —
 * reads as a distinct, warmer coda after the closing's declarative statement,
 * not a repeat of it.
 *
 * logbook #39, round 8: cta ("Follow us...") and handle (the full @handle,
 * spelled out — Section 12) render here now, after invite, in the same
 * typographic treatment CarouselClosing originally used for them (cta at real
 * body-copy weight, handle as a tiny letter-spaced uppercase footnote) —
 * relocated from CarouselClosing, which was rendering them a slide too early,
 * a leftover from before this slide existed.
 */
export default function ConversationSlide({
  masthead,
  tokens,
  label,
  question,
  invite,
  cta,
  handle,
}: ConversationSlideProps) {
  return (
    <SlideFrame backgroundColor={tokens.background_color}>
      <Masthead masthead={masthead} tokens={tokens} />

      <div
        style={{
          display: "flex",
          flex: 1,
          flexDirection: "column",
          justifyContent: "center",
          gap: 24,
        }}
      >
        <span
          style={{
            fontFamily: tokens.font_body,
            fontWeight: 600,
            fontSize: 22,
            letterSpacing: 1,
            color: tokens.accent,
          }}
        >
          {label}
        </span>
        <span
          style={{
            fontFamily: tokens.font_body,
            fontWeight: 700,
            fontSize: 52,
            lineHeight: 1.3,
            color: tokens.text_color,
          }}
        >
          {question}
        </span>
        <span
          style={{
            fontFamily: tokens.font_script,
            fontSize: 40,
            color: tokens.accent,
          }}
        >
          {invite}
        </span>
        <span
          style={{
            fontFamily: tokens.font_body,
            fontWeight: 400,
            fontSize: 24,
            lineHeight: 1.4,
            color: tokens.text_color,
          }}
        >
          {cta}
        </span>
        <span
          style={{
            fontFamily: tokens.font_body,
            fontWeight: 600,
            fontSize: 16,
            letterSpacing: 3,
            textTransform: "uppercase",
            color: tokens.text_color,
            opacity: 0.65,
          }}
        >
          {handle}
        </span>
      </div>
    </SlideFrame>
  );
}
