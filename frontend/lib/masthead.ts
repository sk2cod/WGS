import type { MastheadInfo } from "./types";

/** Parses the backend's formatted masthead string ("WGS — MINDSET NO. 14") into the
 * structured MastheadInfo the render contract (Section 8) expects. */
export function parseMasthead(masthead: string): MastheadInfo {
  const [shortPart, rest] = masthead.split(" — ");
  const match = rest?.match(/^(.*) NO\. (\d+)$/);
  return {
    masthead_short: shortPart?.trim() ?? "",
    category: match?.[1]?.trim() ?? "",
    number: match?.[2] ?? "",
  };
}
