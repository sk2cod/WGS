import { resolveTokens } from "@/lib/brand-tokens";
import { WGS_BRAND_KIT } from "@/lib/wgs-brand-kit";
import type { Mood } from "@/lib/types";
import {
  PLACEHOLDER_MASTHEAD,
  PLACEHOLDER_COVER,
  PLACEHOLDER_BODY,
  PLACEHOLDER_BODY_TEACHING,
  PLACEHOLDER_CLOSING,
  PLACEHOLDER_QUOTE,
  PLACEHOLDER_STAT,
} from "@/lib/placeholder-content";
import CarouselCover from "@/components/slides/CarouselCover";
import CarouselBody from "@/components/slides/CarouselBody";
import CarouselBodyTeaching from "@/components/slides/CarouselBodyTeaching";
import CarouselClosing from "@/components/slides/CarouselClosing";
import SingleQuote from "@/components/slides/SingleQuote";
import SingleStat from "@/components/slides/SingleStat";
import ScaledSlide from "@/components/ui/ScaledSlide";

const MOODS: Mood[] = ["wisdom", "bold", "celebratory"];
const SCALE = 0.28;

export default function PreviewPage() {
  return (
    <main
      style={{
        padding: 32,
        fontFamily: "Inter, sans-serif",
        color: "#171717",
      }}
    >
      <h1 style={{ marginBottom: 4 }}>Template Preview</h1>
      <p style={{ marginBottom: 32, opacity: 0.7 }}>
        All 6 templates × all 3 moods, dummy WGS copy. Layout, fonts, and
        masthead should stay identical across a row — only the duotone pair
        and accent color shift.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: `160px repeat(${MOODS.length}, max-content)`,
          rowGap: 24,
          columnGap: 24,
          alignItems: "start",
        }}
      >
        <RowLabel>&nbsp;</RowLabel>
        {MOODS.map((mood) => (
          <div key={mood} style={{ fontWeight: 700, textTransform: "capitalize" }}>
            {mood}
          </div>
        ))}

        <RowLabel>Carousel Cover</RowLabel>
        {MOODS.map((mood) => (
          <ScaledSlide key={mood} scale={SCALE}>
            <CarouselCover
              masthead={PLACEHOLDER_MASTHEAD}
              tokens={resolveTokens(WGS_BRAND_KIT, mood)}
              {...PLACEHOLDER_COVER}
            />
          </ScaledSlide>
        ))}

        <RowLabel>Carousel Body</RowLabel>
        {MOODS.map((mood) => (
          <ScaledSlide key={mood} scale={SCALE}>
            <CarouselBody
              masthead={PLACEHOLDER_MASTHEAD}
              tokens={resolveTokens(WGS_BRAND_KIT, mood)}
              {...PLACEHOLDER_BODY}
            />
          </ScaledSlide>
        ))}

        <RowLabel>Carousel Body (Teaching)</RowLabel>
        {MOODS.map((mood) => (
          <ScaledSlide key={mood} scale={SCALE}>
            <CarouselBodyTeaching
              masthead={PLACEHOLDER_MASTHEAD}
              tokens={resolveTokens(WGS_BRAND_KIT, mood)}
              {...PLACEHOLDER_BODY_TEACHING}
            />
          </ScaledSlide>
        ))}

        <RowLabel>Carousel Closing</RowLabel>
        {MOODS.map((mood) => (
          <ScaledSlide key={mood} scale={SCALE}>
            <CarouselClosing
              masthead={PLACEHOLDER_MASTHEAD}
              tokens={resolveTokens(WGS_BRAND_KIT, mood)}
              {...PLACEHOLDER_CLOSING}
            />
          </ScaledSlide>
        ))}

        <RowLabel>Single Quote</RowLabel>
        {MOODS.map((mood) => (
          <ScaledSlide key={mood} scale={SCALE}>
            <SingleQuote
              masthead={PLACEHOLDER_MASTHEAD}
              tokens={resolveTokens(WGS_BRAND_KIT, mood)}
              {...PLACEHOLDER_QUOTE}
            />
          </ScaledSlide>
        ))}

        <RowLabel>Single Stat</RowLabel>
        {MOODS.map((mood) => (
          <ScaledSlide key={mood} scale={SCALE}>
            <SingleStat
              masthead={PLACEHOLDER_MASTHEAD}
              tokens={resolveTokens(WGS_BRAND_KIT, mood)}
              {...PLACEHOLDER_STAT}
            />
          </ScaledSlide>
        ))}
      </div>
    </main>
  );
}

function RowLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontWeight: 700, alignSelf: "center" }}>{children}</div>
  );
}
