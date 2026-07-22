import type { MastheadInfo, ResolvedTokens, SingleQuoteContent } from "@/lib/types";
import Masthead from "./Masthead";
import SlideFrame from "./SlideFrame";

interface SingleQuoteProps extends SingleQuoteContent {
  masthead: MastheadInfo;
  tokens: ResolvedTokens;
}

/**
 * No photo — an oversized translucent script quotation mark sits behind the quote text.
 *
 * Fixed: this block used to be top-anchored (fixed marginTop, no vertical
 * centering) with nothing below it to fill the rest of the canvas — unlike
 * every other flex:1-centered template, a short quote left large, empty
 * space in the bottom half of the slide on a real Satori render
 * (docs/logbook.md). Now flex:1 + justifyContent:"center", matching the
 * convention CarouselBody/CarouselBodyTeaching/CarouselClosing/
 * ConversationSlide/SingleStat already use.
 */
export default function SingleQuote({ masthead, tokens, quote }: SingleQuoteProps) {
  return (
    <SlideFrame backgroundColor={tokens.background_color}>
      <Masthead masthead={masthead} tokens={tokens} />

      <div
        style={{
          display: "flex",
          flex: 1,
          flexDirection: "column",
          justifyContent: "center",
          position: "relative",
        }}
      >
        <span
          style={{
            position: "absolute",
            top: -24,
            left: -16,
            fontFamily: tokens.font_script,
            fontSize: 420,
            lineHeight: 1,
            color: tokens.accent,
            opacity: 0.28,
          }}
        >
          &ldquo;
        </span>
        <span
          style={{
            fontFamily: tokens.font_body,
            fontWeight: 600,
            fontSize: 52,
            lineHeight: 1.35,
            color: tokens.text_color,
            marginTop: 48,
          }}
        >
          {quote}
        </span>
      </div>
    </SlideFrame>
  );
}
