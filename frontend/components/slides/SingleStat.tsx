import type { MastheadInfo, ResolvedTokens, SingleStatContent } from "@/lib/types";
import Masthead from "./Masthead";
import SlideFrame from "./SlideFrame";

interface SingleStatProps extends SingleStatContent {
  masthead: MastheadInfo;
  tokens: ResolvedTokens;
}

/** No photo — a small kicker, a huge number in the structural font, one supporting line. */
export default function SingleStat({
  masthead,
  tokens,
  kicker,
  number,
  supporting_line,
}: SingleStatProps) {
  return (
    <SlideFrame backgroundColor={tokens.background_color}>
      <Masthead masthead={masthead} tokens={tokens} />

      <div
        style={{
          display: "flex",
          flex: 1,
          flexDirection: "column",
          justifyContent: "center",
          gap: 20,
        }}
      >
        <span
          style={{
            fontFamily: tokens.font_body,
            fontWeight: 600,
            fontSize: 24,
            letterSpacing: 3,
            textTransform: "uppercase",
            color: tokens.text_color,
            opacity: 0.65,
          }}
        >
          {kicker}
        </span>
        <span
          style={{
            fontFamily: tokens.font_heading,
            fontSize: 200,
            lineHeight: 1,
            color: tokens.accent,
          }}
        >
          {number}
        </span>
        <span
          style={{
            fontFamily: tokens.font_body,
            fontWeight: 400,
            fontSize: 32,
            lineHeight: 1.4,
            color: tokens.text_color,
          }}
        >
          {supporting_line}
        </span>
      </div>
    </SlideFrame>
  );
}
