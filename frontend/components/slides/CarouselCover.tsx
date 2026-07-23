import type { CarouselCoverContent, MastheadInfo, ResolvedTokens } from "@/lib/types";
import Masthead from "./Masthead";
import SlideFrame from "./SlideFrame";

interface CarouselCoverProps extends CarouselCoverContent {
  masthead: MastheadInfo;
  tokens: ResolvedTokens;
}

/** The only template that carries a photo — a duotoned hero anchored to the bottom.
 * headline_word always renders (the same 96px slot legacy's one-word headline used,
 * now also holding direct-write's short headline phrase — task "#19"). script_word
 * and kicker (legacy) and cover_body (direct-write) are each rendered only when
 * present, so an empty legacy field or an unused direct-write field never leaves a
 * blank line's worth of reserved vertical space in the flow.
 *
 * Task "#23": airier line-heights on the multi-word headline and cover_body (both
 * now routinely wrap 2-3 lines since #19, unlike the original one-word headline);
 * a swipe marker between the text block and the hero image, since this is the one
 * template with room to signal "more slides follow" before the photo takes over. */
export default function CarouselCover({
  masthead,
  tokens,
  headline_word,
  script_word,
  kicker,
  cover_body,
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
            lineHeight: 1.1,
            color: tokens.accent,
            textTransform: "uppercase",
          }}
        >
          {headline_word}
        </span>
        {script_word ? (
          <span
            style={{
              fontFamily: tokens.font_script,
              fontSize: 72,
              lineHeight: 1.2,
              color: tokens.text_color,
              marginTop: 8,
            }}
          >
            {script_word}
          </span>
        ) : null}
        {kicker ? (
          <span
            style={{
              fontFamily: tokens.font_body,
              fontSize: 30,
              fontWeight: 400,
              lineHeight: 1.4,
              color: tokens.text_color,
              marginTop: 24,
            }}
          >
            {kicker}
          </span>
        ) : null}
        {cover_body ? (
          <span
            style={{
              fontFamily: tokens.font_body,
              fontSize: 30,
              fontWeight: 400,
              lineHeight: 1.5,
              color: tokens.text_color,
              marginTop: 24,
            }}
          >
            {cover_body}
          </span>
        ) : null}
      </div>

      {/* Swipe marker (task "#23") -- plain ASCII text only, deliberately not a
          Unicode arrow/dot glyph or a CSS-drawn shape: this project's bundled
          font subset has already been found missing glyphs for em dash,
          middot, and hedera/star (logbook #39 round 7), and a first attempt
          at a CSS border-triangle here rendered as a plain filled square
          instead of a triangle on a real Satori render -- Satori's border
          implementation doesn't replicate a browser's diagonal border-miter
          clipping. Plain text avoids both risks entirely. */}
      <div
        style={{
          display: "flex",
          marginTop: 32,
        }}
      >
        <span
          style={{
            fontFamily: tokens.font_body,
            fontSize: 16,
            fontWeight: 600,
            letterSpacing: 3,
            textTransform: "uppercase",
            color: tokens.text_color,
            opacity: 0.5,
          }}
        >
          Swipe {">"}
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
