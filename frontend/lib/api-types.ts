import type {
  CarouselBodyContent,
  CarouselBodyTeachingContent,
  CarouselClosingContent,
  CarouselCoverContent,
  Mood,
  SingleQuoteContent,
  SingleStatContent,
} from "./types";

export type ApiFormat = "carousel" | "single_image";
export type Approach =
  | "educational"
  | "myth_vs_fact"
  | "checklist"
  | "story"
  | "stat_research"
  | "question_reflection"
  | "framework"
  | "common_mistakes";
export type Sensitivity = "normal" | "health" | "sensitive";

export interface Source {
  title: string;
  author?: string | null;
  url?: string | null;
  excerpt: string;
  retrieved_at: string;
}

export interface ContentBrief {
  topic_id: string;
  topic_name: string;
  angle: string;
  approach: Approach;
  goal: string;
  mood: Mood;
  format: ApiFormat;
  slide_count: number;
  tone: string[];
  brand_voice_samples: string[];
  signature_cta?: string | null;
  requires_citation: boolean;
  sensitivity: Sensitivity;
  sources: Source[];
  // Grounding for requires_citation topics with no pinned Source objects (i.e.
  // everything except the paste-link flow) — mirrors backend/app/models/brief.py
  // (fix #14, docs/logbook.md).
  knowledge_hints: string[];
  hero_image_prompt: string;
  max_words_per_slide: number;
}

// The discriminated slide union — mirrors backend/app/models/post.py exactly, reusing
// the render-contract content shapes from lib/types.ts (template_id is the only field
// they don't already carry, since a raw render request only needs it once at the top
// level; the API needs it per-slide to route each slide to its own /api/render call).
export interface ApiCoverSlide extends CarouselCoverContent {
  template_id: "carousel_cover";
}
export interface ApiBodySlide extends CarouselBodyContent {
  template_id: "carousel_body";
}
export interface ApiBodyTeachingSlide extends CarouselBodyTeachingContent {
  template_id: "carousel_body_teaching";
}
export interface ApiClosingSlide extends CarouselClosingContent {
  template_id: "carousel_closing";
}
export interface ApiQuoteSlide extends SingleQuoteContent {
  template_id: "single_quote";
}
export interface ApiStatSlide extends SingleStatContent {
  template_id: "single_stat";
}

export type ApiSlide =
  | ApiCoverSlide
  | ApiBodySlide
  | ApiBodyTeachingSlide
  | ApiClosingSlide
  | ApiQuoteSlide
  | ApiStatSlide;

export interface GeneratedPost {
  slides: ApiSlide[];
  caption: string;
  hashtags: string[];
}

export interface Topic {
  id: string;
  name: string;
  categories: string[];
  primary_category: string;
  tone_defaults: string[];
  suitable_formats: ApiFormat[];
  seed_angles: string[];
  knowledge_hints: string[];
  requires_citation: boolean;
  sensitivity: Sensitivity;
}

export interface ProposeResponse {
  topic_id: string;
  topic_name: string;
  angle: string;
  approach: Approach;
  mood: Mood;
  reason: string;
  visual_subject: string;
  fingerprint: string;
}

export interface GenerateResponse {
  brief: ContentBrief;
  post: GeneratedPost;
  masthead: string;
  hero_image_base64: string | null;
  validation_errors: string[];
}

export interface DailyPick {
  topic_id: string;
  topic_name: string;
  category: string;
  source_type: "evergreen" | "timely";
  approach: Approach;
  mood: Mood;
  angle: string;
  hook: string;
  thumbnail_concept: string;
  awareness_day_name?: string | null;
}

export interface DailyPicksResult {
  date: string;
  picks: DailyPick[];
  rerolls_used: number;
}

export interface PasteLinkBriefResult {
  brief: ContentBrief;
  masthead: string;
}
