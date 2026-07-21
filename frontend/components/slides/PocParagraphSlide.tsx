import type { MastheadInfo, ResolvedTokens } from "@/lib/types";
import Masthead from "./Masthead";
import SlideFrame from "./SlideFrame";

interface PocParagraphSlideProps {
  text: string;
  masthead: MastheadInfo;
  tokens: ResolvedTokens;
}

/**
 * POC-only slide template (isolated experiment, not part of the six locked
 * carousel/single-image templates). Deliberately has no headline, kicker, or any
 * fixed sub-part — just one flowing paragraph, centered on the page. Reuses only
 * SlideFrame (canvas/padding) and Masthead (top-corner brand mark) from the
 * existing template set; everything else here is new.
 *
 * Font size is picked from the paragraph's length so a short beat reads large and
 * a long one still fits without overflowing the fixed 1080x1350 canvas — Satori's
 * CSS subset has no clamp()/container queries, so this is done in JS instead.
 */
function paragraphFontSize(text: string): number {
  const len = text.length;
  if (len < 100) return 58;
  if (len < 180) return 50;
  if (len < 260) return 42;
  if (len < 340) return 36;
  if (len < 420) return 32;
  return 28;
}

export default function PocParagraphSlide({ text, masthead, tokens }: PocParagraphSlideProps) {
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
        <span
          style={{
            fontFamily: tokens.font_body,
            fontWeight: 500,
            fontSize: paragraphFontSize(text),
            lineHeight: 1.45,
            color: tokens.text_color,
          }}
        >
          {text}
        </span>
      </div>
    </SlideFrame>
  );
}
