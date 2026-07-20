import type { NextRequest } from "next/server";
import { loadSlideFonts } from "@/lib/fonts";
import { CANVAS_WIDTH, CANVAS_HEIGHT } from "@/lib/canvas";
import CarouselCover from "@/components/slides/CarouselCover";
import CarouselBody from "@/components/slides/CarouselBody";
import CarouselBodyTeaching from "@/components/slides/CarouselBodyTeaching";
import CarouselClosing from "@/components/slides/CarouselClosing";
import ConversationSlide from "@/components/slides/ConversationSlide";
import SingleQuote from "@/components/slides/SingleQuote";
import SingleStat from "@/components/slides/SingleStat";
import type {
  CarouselBodyContent,
  CarouselBodyTeachingContent,
  CarouselClosingContent,
  CarouselConversationContent,
  CarouselCoverContent,
  RenderRequestBody,
  SingleQuoteContent,
  SingleStatContent,
} from "@/lib/types";

// Reads local font files via node:fs (lib/fonts.ts) — needs the Node runtime, not Edge.
export const runtime = "nodejs";

function badRequest(message: string) {
  return new Response(JSON.stringify({ error: message }), {
    status: 400,
    headers: { "content-type": "application/json" },
  });
}

/**
 * The render contract (Section 8): backend hands over an already-resolved
 * mood palette + typed slide content, this route rasterizes it with Satori.
 * The JSX slide templates are the single source of truth — the same
 * components render live in the editor and to PNG here.
 */
export async function POST(req: NextRequest) {
  let body: RenderRequestBody;
  try {
    body = (await req.json()) as RenderRequestBody;
  } catch {
    return badRequest("invalid JSON body");
  }

  const { template_id, slides, masthead, tokens, hero_image_url } = body;

  if (!masthead || !tokens) {
    return badRequest("masthead and tokens are required");
  }
  if (!Array.isArray(slides) || slides.length === 0) {
    return badRequest("slides must be a non-empty array");
  }

  const content = slides[0];

  let element: React.ReactElement;
  switch (template_id) {
    case "carousel_cover": {
      const c = content as CarouselCoverContent;
      element = (
        <CarouselCover
          masthead={masthead}
          tokens={tokens}
          headline_word={c.headline_word}
          script_word={c.script_word}
          kicker={c.kicker}
          hero_image_url={c.hero_image_url ?? hero_image_url ?? null}
        />
      );
      break;
    }
    case "carousel_body": {
      const c = content as CarouselBodyContent;
      element = <CarouselBody masthead={masthead} tokens={tokens} {...c} />;
      break;
    }
    case "carousel_body_teaching": {
      const c = content as CarouselBodyTeachingContent;
      element = <CarouselBodyTeaching masthead={masthead} tokens={tokens} {...c} />;
      break;
    }
    case "carousel_closing": {
      const c = content as CarouselClosingContent;
      element = <CarouselClosing masthead={masthead} tokens={tokens} {...c} />;
      break;
    }
    case "carousel_conversation": {
      const c = content as CarouselConversationContent;
      element = <ConversationSlide masthead={masthead} tokens={tokens} {...c} />;
      break;
    }
    case "single_quote": {
      const c = content as SingleQuoteContent;
      element = <SingleQuote masthead={masthead} tokens={tokens} {...c} />;
      break;
    }
    case "single_stat": {
      const c = content as SingleStatContent;
      element = <SingleStat masthead={masthead} tokens={tokens} {...c} />;
      break;
    }
    default:
      return badRequest(`unknown template_id: ${template_id}`);
  }

  try {
    const { ImageResponse } = await import("@vercel/og");
    const fonts = await loadSlideFonts();
    return new ImageResponse(element, {
      width: CANVAS_WIDTH,
      height: CANVAS_HEIGHT,
      fonts,
    });
  } catch (err) {
    console.error("render failed:", err);
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : String(err) }),
      { status: 500, headers: { "content-type": "application/json" } },
    );
  }
}
