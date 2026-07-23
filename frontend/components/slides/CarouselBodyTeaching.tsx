import type { CarouselBodyTeachingContent, MastheadInfo, ResolvedTokens } from "@/lib/types";
import Masthead from "./Masthead";
import SlideFrame from "./SlideFrame";

interface CarouselBodyTeachingProps extends CarouselBodyTeachingContent {
  masthead: MastheadInfo;
  tokens: ResolvedTokens;
}

/** No photo — room for 1-2 full sentences of actual teaching content, distinct from
 * CarouselBody's single emphasis-fragment statement (which can't hold real substance).
 *
 * heading (legacy) renders only when present. The carousel direct-write port (task
 * "#19") drops heading entirely and supplies accent_phrase instead — an exact
 * substring of `body` — rendered in-line in the mood's accent color using the same
 * word-flex technique CarouselBody.tsx already uses for its own single emphasized
 * phrase. Falls back to a plain, unsplit body render whenever accent_phrase is empty
 * or isn't actually found in body (a real possibility, not assumed away), so a
 * miss here degrades to legacy's original look rather than rendering nothing. */
export default function CarouselBodyTeaching({
  masthead,
  tokens,
  heading,
  body,
  accent_phrase,
}: CarouselBodyTeachingProps) {
  const accentIndex = accent_phrase ? body.indexOf(accent_phrase) : -1;
  const bodyTextStyle = {
    fontFamily: tokens.font_body,
    fontWeight: 500,
    fontSize: 44, // task "#23": up from 36 -- real render showed even the 55-word
    // ceiling case left roughly half the frame empty at 36px; a real, fixed size
    // bump (not per-length, that's reserved for Closing) makes any amount of real
    // content within the template's actual word range read as more substantial,
    // on top of the top-anchor layout change and the line-height increase below.
    lineHeight: 1.6, // airier reading
    color: tokens.text_color,
  };

  // The flex-wrap word-splitting technique below puts a fixed columnGap between
  // EVERY pair of adjacent spans, which is only correct where the source text
  // actually had a space -- confirmed by a real render (task "#19") to leave a
  // stray visible gap before trailing punctuation glued directly onto the
  // accent phrase with no space (e.g. "...far less convenient ." instead of
  // "...far less convenient."). Any such punctuation is pulled into the accent
  // span itself instead, so it shares the accent span's own flex item and gets
  // no columnGap before it.
  let leadGlue = "";
  let trailGlue = "";
  let preText = "";
  let postText = "";
  if (accentIndex !== -1 && accent_phrase) {
    const rawPre = body.slice(0, accentIndex);
    const rawPost = body.slice(accentIndex + accent_phrase.length);
    if (rawPre.length > 0 && !rawPre.endsWith(" ")) {
      const spaceIdx = rawPre.lastIndexOf(" ");
      leadGlue = rawPre.slice(spaceIdx + 1);
      preText = rawPre.slice(0, spaceIdx + 1);
    } else {
      preText = rawPre;
    }
    if (rawPost.length > 0 && !rawPost.startsWith(" ")) {
      const spaceIdx = rawPost.indexOf(" ");
      trailGlue = spaceIdx === -1 ? rawPost : rawPost.slice(0, spaceIdx);
      postText = spaceIdx === -1 ? "" : rawPost.slice(spaceIdx);
    } else {
      postText = rawPost;
    }
  }

  return (
    <SlideFrame backgroundColor={tokens.background_color}>
      <Masthead masthead={masthead} tokens={tokens} />

      {/* Task "#23": top-anchored (flex-start + a fixed marginTop, same convention
          Cover already uses) instead of vertically centered -- a centered block
          reads as a small floating island surrounded by equal empty margins top
          and bottom, and that "island" shrinks or grows with word count instead of
          the frame consistently filling from a fixed reading position. A real
          deviation from blueprint.md Section 12's own "center within that wrapper"
          convention for this template family -- logged, not silently reverted. */}
      <div
        style={{
          display: "flex",
          flex: 1,
          flexDirection: "column",
          justifyContent: "flex-start",
          marginTop: 56,
          gap: 24,
        }}
      >
        {heading ? (
          <span
            style={{
              fontFamily: tokens.font_heading,
              fontSize: 40,
              lineHeight: 1.25,
              color: tokens.accent,
              textTransform: "uppercase",
            }}
          >
            {heading}
          </span>
        ) : null}
        {accentIndex === -1 ? (
          <span style={bodyTextStyle}>{body}</span>
        ) : (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "baseline",
              columnGap: 10,
              rowGap: 6,
            }}
          >
            {preText
              .split(" ")
              .filter(Boolean)
              .map((word, i) => (
                <span key={`pre-${i}`} style={bodyTextStyle}>
                  {word}
                </span>
              ))}
            <span style={{ ...bodyTextStyle, color: tokens.accent }}>
              {leadGlue}
              {accent_phrase}
              {trailGlue}
            </span>
            {postText
              .split(" ")
              .filter(Boolean)
              .map((word, i) => (
                <span key={`post-${i}`} style={bodyTextStyle}>
                  {word}
                </span>
              ))}
          </div>
        )}
      </div>
    </SlideFrame>
  );
}
