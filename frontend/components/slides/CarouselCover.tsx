import type { CarouselCoverContent, MastheadInfo, ResolvedTokens } from "@/lib/types";
import Masthead from "./Masthead";
import SlideFrame from "./SlideFrame";

interface CarouselCoverProps extends CarouselCoverContent {
  masthead: MastheadInfo;
  tokens: ResolvedTokens;
}

/** The only template that carries a photo — a duotoned hero anchored to the bottom. */
export default function CarouselCover({
  masthead,
  tokens,
  headline_word,
  script_word,
  kicker,
  hero_image_url,
}: CarouselCoverProps) {
  return (
    <SlideFrame backgroundColor={tokens.background_color}>
      <Masthead masthead={masthead} tokens={tokens} />

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          marginTop: 56,
        }}
      >
        <span
          style={{
            fontFamily: tokens.font_heading,
            fontSize: 96,
            lineHeight: 1,
            color: tokens.accent,
            textTransform: "uppercase",
          }}
        >
          {headline_word}
        </span>
        <span
          style={{
            fontFamily: tokens.font_script,
            fontSize: 72,
            lineHeight: 1.15,
            color: tokens.text_color,
            marginTop: 8,
          }}
        >
          {script_word}
        </span>
        <span
          style={{
            fontFamily: tokens.font_body,
            fontSize: 30,
            fontWeight: 400,
            color: tokens.text_color,
            marginTop: 24,
          }}
        >
          {kicker}
        </span>
      </div>

      {/* Hero photo anchored to the bottom via marginTop: auto. Real image
          arrives in Phase 3; for now a mood-duotoned gradient stands in. */}
      <div
        style={{
          display: "flex",
          marginTop: "auto",
          width: "100%",
          height: 620,
          borderRadius: 16,
          backgroundImage: hero_image_url
            ? `url(${hero_image_url})`
            : `linear-gradient(135deg, ${tokens.primary}, ${tokens.secondary})`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      />
    </SlideFrame>
  );
}
