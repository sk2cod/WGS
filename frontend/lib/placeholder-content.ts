import type {
  CarouselBodyContent,
  CarouselClosingContent,
  CarouselCoverContent,
  MastheadInfo,
  SingleQuoteContent,
  SingleStatContent,
} from "./types";
import { WGS_BRAND_KIT } from "./wgs-brand-kit";

// Dummy WGS-voiced content used by /preview and for exercising /api/render
// before any real generation pipeline exists.
export const PLACEHOLDER_MASTHEAD: MastheadInfo = {
  masthead_short: WGS_BRAND_KIT.masthead_short,
  category: "MINDSET",
  number: "14",
};

export const PLACEHOLDER_COVER: CarouselCoverContent = {
  headline_word: "PAUSE",
  script_word: "first.",
  kicker: "Before you react, breathe.",
  hero_image_url: null,
};

export const PLACEHOLDER_BODY: CarouselBodyContent = {
  statement_pre: "Confidence isn't a feeling you",
  statement_script: "wait for.",
  statement_post: "It's a skill you build one uncomfortable conversation at a time.",
};

export const PLACEHOLDER_CLOSING: CarouselClosingContent = {
  takeaway: "You don't have to shrink to keep the peace.",
  signature: "with you,",
  cta: WGS_BRAND_KIT.signature_cta ?? "",
  handle: WGS_BRAND_KIT.handle,
};

export const PLACEHOLDER_QUOTE: SingleQuoteContent = {
  quote: "Growth doesn't announce itself. It just quietly becomes the way you breathe.",
};

export const PLACEHOLDER_STAT: SingleStatContent = {
  kicker: "Did you know",
  number: "73%",
  supporting_line: "of women report being interrupted more often in meetings than men.",
};
