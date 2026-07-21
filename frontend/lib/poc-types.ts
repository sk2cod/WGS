// Types for the isolated POC endpoint (POST /poc/generate) only — deliberately
// separate from api-types.ts's GeneratedPost/ApiSlide shapes, which describe the
// real /generate pipeline's discriminated-union slide contract. The POC's shape is
// much simpler: a flat list of paragraphs, not a typed union of six slide roles.

export interface PocGenerateResponse {
  topic_id: string;
  topic_name: string;
  slides: string[]; // 4-7 flowing paragraphs, variable count
  conversation_question: string;
  caption: string;
}
