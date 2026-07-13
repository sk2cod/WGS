import type { MastheadInfo, ResolvedTokens, SingleQuoteContent } from "@/lib/types";
import Masthead from "./Masthead";
import SlideFrame from "./SlideFrame";

interface SingleQuoteProps extends SingleQuoteContent {
  masthead: MastheadInfo;
  tokens: ResolvedTokens;
}

/** No photo — an oversized translucent script quotation mark sits behind the quote text. */
export default function SingleQuote({ masthead, tokens, quote }: SingleQuoteProps) {
  return (
    <SlideFrame backgroundColor={tokens.background_color}>
      <Masthead masthead={masthead} tokens={tokens} />

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          position: "relative",
          marginTop: 56,
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
            marginTop: 240,
          }}
        >
          {quote}
        </span>
      </div>
    </SlideFrame>
  );
}
