import type { CarouselBodyContent, MastheadInfo, ResolvedTokens } from "@/lib/types";
import Masthead from "./Masthead";
import SlideFrame from "./SlideFrame";

interface CarouselBodyProps extends CarouselBodyContent {
  masthead: MastheadInfo;
  tokens: ResolvedTokens;
}

/** No photo — a large statement with one script-accent phrase for emphasis. */
export default function CarouselBody({
  masthead,
  tokens,
  statement_pre,
  statement_script,
  statement_post,
}: CarouselBodyProps) {
  return (
    <SlideFrame backgroundColor={tokens.background_color}>
      <Masthead masthead={masthead} tokens={tokens} />

      <div
        style={{
          display: "flex",
          flex: 1,
          flexDirection: "column",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "baseline",
            columnGap: 16,
            rowGap: 8,
          }}
        >
          {statement_pre.split(" ").map((word, i) => (
            <span
              key={`pre-${i}`}
              style={{
                fontFamily: tokens.font_body,
                fontWeight: 700,
                fontSize: 56,
                lineHeight: 1.25,
                color: tokens.text_color,
              }}
            >
              {word}
            </span>
          ))}
          <span
            style={{
              fontFamily: tokens.font_script,
              fontWeight: 400,
              fontSize: 64,
              lineHeight: 1.25,
              color: tokens.accent,
            }}
          >
            {statement_script}
          </span>
          {statement_post.split(" ").map((word, i) => (
            <span
              key={`post-${i}`}
              style={{
                fontFamily: tokens.font_body,
                fontWeight: 700,
                fontSize: 56,
                lineHeight: 1.25,
                color: tokens.text_color,
              }}
            >
              {word}
            </span>
          ))}
        </div>
      </div>
    </SlideFrame>
  );
}
