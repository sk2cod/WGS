export type Mood = "wisdom" | "bold" | "celebratory";

export interface MoodPalette {
  primary: string; // hex — duotone shadow
  secondary: string; // hex — duotone highlight
  accent: string; // hex — script word, masthead rule, CTAs
}

export interface VoiceRegister {
  poetic: string[];
  direct: string[];
}

export interface BrandKit {
  brand_name: string;
  handle: string;
  masthead_short: string;
  niche: string;
  audience: string;

  voice_traits: string[];
  voice_samples: VoiceRegister;
  forbidden: string[];

  mood_palettes: Record<Mood, MoodPalette>;
  text_color: string;
  background_color: string;
  font_heading: string;
  font_script: string;
  font_body: string;

  default_tone: string[];
  signature_cta?: string | null;
}

/** The already-resolved tokens the render contract (Section 8) expects — never the raw BrandKit. */
export interface ResolvedTokens {
  primary: string;
  secondary: string;
  accent: string;
  text_color: string;
  background_color: string;
  font_heading: string;
  font_script: string;
  font_body: string;
}

export interface MastheadInfo {
  masthead_short: string;
  category: string;
  number: string; // e.g. "14" — Masthead.tsx formats the full "{category} NO. {n}" string
}

export type TemplateId =
  | "carousel_cover"
  | "carousel_body"
  | "carousel_closing"
  | "single_quote"
  | "single_stat";

export interface CarouselCoverContent {
  headline_word: string;
  script_word: string;
  kicker: string;
  hero_image_url?: string | null;
}

export interface CarouselBodyContent {
  statement_pre: string;
  statement_script: string;
  statement_post: string;
}

export interface CarouselClosingContent {
  takeaway: string;
  signature: string;
  cta: string;
  handle: string; // full @handle, spelled out only here (Section 12)
}

export interface SingleQuoteContent {
  quote: string;
}

export interface SingleStatContent {
  kicker: string;
  number: string;
  supporting_line: string;
}

export type SlideContent =
  | CarouselCoverContent
  | CarouselBodyContent
  | CarouselClosingContent
  | SingleQuoteContent
  | SingleStatContent;

export interface RenderRequestBody {
  template_id: TemplateId;
  slides: SlideContent[];
  masthead: MastheadInfo;
  tokens: ResolvedTokens;
  hero_image_url?: string | null;
}
