import type {
  ApiFormat,
  ApiSlide,
  Approach,
  ContentBrief,
  DailyPicksResult,
  ExportConfirmResponse,
  GeneratedPost,
  GenerateResponse,
  PasteLinkBriefResult,
  ProposeResponse,
  SingleImageStyle,
  Topic,
} from "./api-types";
import type { Mood } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new ApiError(res.status, detail || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export { ApiError };

export function getTopics(): Promise<Topic[]> {
  return request<Topic[]>("/topics");
}

export function getDailyPicks(): Promise<DailyPicksResult> {
  return request<DailyPicksResult>("/picks");
}

export function rerollPick(pickIndex: number): Promise<DailyPicksResult> {
  return request<DailyPicksResult>("/picks/reroll", {
    method: "POST",
    body: JSON.stringify({ pick_index: pickIndex }),
  });
}

export function pasteLink(url: string, format: ApiFormat = "carousel"): Promise<PasteLinkBriefResult> {
  return request<PasteLinkBriefResult>("/sources/paste-link", {
    method: "POST",
    body: JSON.stringify({ url, format }),
  });
}

export function proposeApproach(
  topicId: string,
  format: ApiFormat,
  singleImageStyle?: SingleImageStyle,
): Promise<ProposeResponse> {
  return request<ProposeResponse>("/generate/propose", {
    method: "POST",
    body: JSON.stringify({ topic_id: topicId, format, single_image_style: singleImageStyle ?? null }),
  });
}

export interface AcceptedProposal {
  angle: string;
  approach: Approach;
  mood: Mood;
  visual_subject: string;
  fingerprint: string;
}

export function generatePost(
  topicId: string,
  format: ApiFormat,
  accepted?: AcceptedProposal,
  singleImageStyle?: SingleImageStyle,
): Promise<GenerateResponse> {
  return request<GenerateResponse>("/generate", {
    method: "POST",
    body: JSON.stringify({
      topic_id: topicId,
      format,
      single_image_style: singleImageStyle ?? null,
      ...accepted,
    }),
  });
}

export function generateFromBrief(
  brief: ContentBrief,
  masthead: string,
  category = "Society",
): Promise<GenerateResponse> {
  return request<GenerateResponse>("/generate/from-brief", {
    method: "POST",
    body: JSON.stringify({ brief, masthead, category }),
  });
}

export function regenerateSlide(
  brief: ContentBrief,
  post: GeneratedPost,
  slideIndex: number,
): Promise<{ slide: ApiSlide }> {
  return request<{ slide: ApiSlide }>("/generate/regenerate-slide", {
    method: "POST",
    body: JSON.stringify({ brief, post, slide_index: slideIndex }),
  });
}

export function reshuffleImage(
  brief: ContentBrief,
  variant: number,
): Promise<{ hero_image_base64: string }> {
  return request<{ hero_image_base64: string }>("/generate/reshuffle-image", {
    method: "POST",
    body: JSON.stringify({ brief, variant }),
  });
}

export function confirmExport(
  memoryId: string,
  caption: string,
  slides: ApiSlide[],
  trainVoice: boolean,
): Promise<ExportConfirmResponse> {
  return request<ExportConfirmResponse>("/export/confirm", {
    method: "POST",
    body: JSON.stringify({
      memory_id: memoryId,
      caption,
      slides,
      train_voice: trainVoice,
    }),
  });
}
