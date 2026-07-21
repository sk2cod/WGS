import type { PocGenerateResponse } from "./poc-types";

// Deliberately not reusing lib/api.ts's internal request() helper (it isn't
// exported) — a small self-contained fetch here keeps the POC fully isolated from
// the real pipeline's API client, per the "new code only" scope for this POC.
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class PocApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "PocApiError";
  }
}

export async function generatePoc(topicId: string): Promise<PocGenerateResponse> {
  const res = await fetch(`${API_URL}/poc/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic_id: topicId }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new PocApiError(res.status, detail || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<PocGenerateResponse>;
}
