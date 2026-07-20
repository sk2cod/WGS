import type { ApiSlide } from "@/lib/api-types";
import type { MastheadInfo, ResolvedTokens } from "@/lib/types";
import CarouselCover from "@/components/slides/CarouselCover";
import CarouselBody from "@/components/slides/CarouselBody";
import CarouselBodyTeaching from "@/components/slides/CarouselBodyTeaching";
import CarouselClosing from "@/components/slides/CarouselClosing";
import ConversationSlide from "@/components/slides/ConversationSlide";
import SingleQuote from "@/components/slides/SingleQuote";
import SingleStat from "@/components/slides/SingleStat";

interface SlideRendererProps {
  slide: ApiSlide;
  masthead: MastheadInfo;
  tokens: ResolvedTokens;
  heroImageUrl?: string | null;
}

/** Picks the right template component for a slide's `template_id` — the same
 * components the editor previews live and /api/render rasterizes to PNG. */
export default function SlideRenderer({ slide, masthead, tokens, heroImageUrl }: SlideRendererProps) {
  switch (slide.template_id) {
    case "carousel_cover":
      return (
        <CarouselCover
          masthead={masthead}
          tokens={tokens}
          headline_word={slide.headline_word}
          script_word={slide.script_word}
          kicker={slide.kicker}
          hero_image_url={heroImageUrl ?? null}
        />
      );
    case "carousel_body":
      return <CarouselBody masthead={masthead} tokens={tokens} {...slide} />;
    case "carousel_body_teaching":
      return <CarouselBodyTeaching masthead={masthead} tokens={tokens} {...slide} />;
    case "carousel_closing":
      return <CarouselClosing masthead={masthead} tokens={tokens} {...slide} />;
    case "carousel_conversation":
      return <ConversationSlide masthead={masthead} tokens={tokens} {...slide} />;
    case "single_quote":
      return <SingleQuote masthead={masthead} tokens={tokens} {...slide} />;
    case "single_stat":
      return <SingleStat masthead={masthead} tokens={tokens} {...slide} />;
    default:
      return null;
  }
}
