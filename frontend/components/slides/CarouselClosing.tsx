import type { CarouselClosingContent, MastheadInfo, ResolvedTokens } from "@/lib/types";
import Masthead from "./Masthead";
import SlideFrame from "./SlideFrame";

interface CarouselClosingProps extends CarouselClosingContent {
  masthead: MastheadInfo;
  tokens: ResolvedTokens;
}

// Task "#23": takeaway is a real 2-4 sentence build now (logbook #53), not the
// one-line takeaway this fixed 48px size was originally tuned for -- scales the
// size down smoothly as word count climbs so a full 4-sentence closing doesn't
// carry the same oversized weight a short one-liner earned. Word-count bounds
// match generator.py's _CAROUSEL_DIRECT_CLOSING_WORD_RANGE tolerant range
// (21-61); Satori has no clamp()/calc() support to lean on, so this is computed
// in JS rather than CSS, same approach the rest of this codebase already uses
// for anything content-length-dependent (e.g. the backend's own word-range checks).
const CLOSING_MIN_WORDS = 21;
const CLOSING_MAX_WORDS = 61;
const CLOSING_MAX_SIZE = 48;
const CLOSING_MIN_SIZE = 36;

function closingFontSize(takeaway: string): number {
  const words = takeaway.trim().split(/\s+/).filter(Boolean).length;
  const clamped = Math.min(Math.max(words, CLOSING_MIN_WORDS), CLOSING_MAX_WORDS);
  const t = (clamped - CLOSING_MIN_WORDS) / (CLOSING_MAX_WORDS - CLOSING_MIN_WORDS);
  return Math.round(CLOSING_MAX_SIZE - t * (CLOSING_MAX_SIZE - CLOSING_MIN_SIZE));
}

/**
 * Background = mood's primary, text = mood's secondary. Masthead stays pinned
 * top in normal flow; everything else lives in its own flex:1 wrapper.
 *
 * Task "#23": top-anchored (flex-start + a fixed marginTop, matching Cover's
 * own convention) instead of vertically centered -- a real deviation from
 * blueprint.md Section 12's "center within that wrapper" convention for this
 * template family, logged not silently reverted (same reasoning as
 * CarouselBodyTeaching's identical change). fontWeight dropped 700 -> 600
 * (too heavy at the original weight) and fontSize is now responsive to
 * takeaway's own length via closingFontSize() above, not fixed at one size.
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
          justifyContent: "flex-start",
          marginTop: 56,
        }}
      >
        <span
          style={{
            fontFamily: tokens.font_body,
            fontWeight: 600,
            fontSize: closingFontSize(takeaway),
            lineHeight: 1.4,
            color: onPrimary,
          }}
        >
          {takeaway}
        </span>
      </div>
    </SlideFrame>
  );
}
