import type { CarouselBodyTeachingContent, MastheadInfo, ResolvedTokens } from "@/lib/types";
import Masthead from "./Masthead";
import SlideFrame from "./SlideFrame";

interface CarouselBodyTeachingProps extends CarouselBodyTeachingContent {
  masthead: MastheadInfo;
  tokens: ResolvedTokens;
}

/** No photo — room for 1-2 full sentences of actual teaching content, distinct from
 * CarouselBody's single emphasis-fragment statement (which can't hold real substance). */
export default function CarouselBodyTeaching({
  masthead,
  tokens,
  heading,
  body,
}: CarouselBodyTeachingProps) {
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
            fontFamily: tokens.font_heading,
            fontSize: 40,
            lineHeight: 1.2,
            color: tokens.accent,
            textTransform: "uppercase",
          }}
        >
          {heading}
        </span>
        <span
          style={{
            fontFamily: tokens.font_body,
            fontWeight: 500,
            fontSize: 36,
            lineHeight: 1.5,
            color: tokens.text_color,
          }}
        >
          {body}
        </span>
      </div>
    </SlideFrame>
  );
}
