"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { generatePost, getTopics, proposeApproach } from "@/lib/api";
import type { ApiFormat, ProposeResponse, SingleImageStyle, Topic } from "@/lib/api-types";
import { saveCurrentPost } from "@/lib/session-store";
import {
  cardStyle,
  ghostButtonStyle,
  labelStyle,
  primaryButtonStyle,
  screenStyle,
  secondaryButtonStyle,
} from "@/lib/ui-styles";

const APPROACH_LABELS: Record<string, string> = {
  educational: "Educational",
  myth_vs_fact: "Myth vs. Fact",
  checklist: "Checklist",
  story: "Story",
  stat_research: "Stat & Research",
  question_reflection: "Reflection",
  framework: "Framework",
  common_mistakes: "Common Mistakes",
};

// Carousel generation runs the direct-write port (docs/logbook.md #43-46):
// one call writes the piece, then the hero image generates AFTER it, not
// alongside it (mood/visual_subject aren't known until the writer call
// returns) -- a real, documented slower-end-to-end tradeoff, not a bug.
// These stages exist so the wait reads as "working through stages," not
// "stuck," while that's happening. Thresholds are a reasonable estimate,
// not measured telemetry -- fine either way since they're reassurance
// text, not a progress bar making a precision claim.
const CAROUSEL_WAIT_STAGES: { at: number; label: string }[] = [
  { at: 0, label: "Writing your carousel — picking its own anchor and drafting the whole piece in one pass…" },
  { at: 15, label: "Still writing — this is a single longer call, not several short ones." },
  { at: 30, label: "Text is likely done — generating the hero image next (that step runs after the writing, not alongside it)." },
  { at: 50, label: "Almost there — styling the hero image now." },
];

function carouselWaitMessage(elapsedSeconds: number): string {
  let message = CAROUSEL_WAIT_STAGES[0].label;
  for (const stage of CAROUSEL_WAIT_STAGES) {
    if (elapsedSeconds >= stage.at) message = stage.label;
  }
  return message;
}

export default function GeneratePage() {
  return (
    <Suspense fallback={null}>
      <GenerateScreen />
    </Suspense>
  );
}

function GenerateScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const topicId = searchParams.get("topic_id");

  const [format, setFormat] = useState<ApiFormat>("carousel");
  const [singleImageStyle, setSingleImageStyle] = useState<SingleImageStyle>("quote");
  const [topics, setTopics] = useState<Topic[] | null>(null);
  const [proposal, setProposal] = useState<ProposeResponse | null>(null);
  const [proposing, setProposing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Only carousel's header needs this -- single_image already gets its topic
  // name from the propose response, unchanged. Fetched once, independent of
  // format/topicId changes.
  useEffect(() => {
    getTopics()
      .then(setTopics)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!topicId) return;
    // Carousel skips the propose/preview step entirely (logbook #50) --
    // direct-write picks its own anchor at generation time, so there is
    // nothing to preview first. single_image's propose-then-accept flow
    // below is completely unchanged.
    if (format === "single_image") {
      void loadProposal();
    } else {
      setProposal(null);
      setError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topicId, format, singleImageStyle]);

  useEffect(() => {
    if (!generating || format !== "carousel") {
      setElapsedSeconds(0);
      return;
    }
    const id = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [generating, format]);

  async function loadProposal() {
    if (!topicId) return;
    setProposing(true);
    setError(null);
    try {
      setProposal(
        await proposeApproach(topicId, format, format === "single_image" ? singleImageStyle : undefined),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setProposing(false);
    }
  }

  async function handleGenerate() {
    if (!topicId) return;
    if (format === "single_image" && !proposal) return;
    setGenerating(true);
    setError(null);
    try {
      const generated = await generatePost(
        topicId,
        format,
        format === "single_image"
          ? {
              angle: proposal!.angle,
              approach: proposal!.approach,
              mood: proposal!.mood,
              visual_subject: proposal!.visual_subject,
              fingerprint: proposal!.fingerprint,
            }
          : undefined,
        format === "single_image" ? singleImageStyle : undefined,
      );
      saveCurrentPost(generated);
      router.push("/editor");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setGenerating(false);
    }
  }

  if (!topicId) {
    return (
      <main style={screenStyle}>
        <p>No topic selected.</p>
        <button style={primaryButtonStyle} onClick={() => router.push("/")}>
          Back home
        </button>
      </main>
    );
  }

  const carouselTopicName = topics?.find((t) => t.id === topicId)?.name;
  const headerTitle = format === "single_image" ? proposal?.topic_name : carouselTopicName;

  return (
    <main style={screenStyle}>
      <header>
        <button style={ghostButtonStyle} onClick={() => router.push("/")}>
          ← Back
        </button>
        <h1 style={{ fontSize: 22, marginTop: 8 }}>{headerTitle ?? "Loading…"}</h1>
      </header>

      <section style={{ display: "flex", gap: 8 }}>
        <button
          style={{ ...(format === "carousel" ? primaryButtonStyle : secondaryButtonStyle), flex: 1 }}
          onClick={() => setFormat("carousel")}
        >
          Carousel
        </button>
        <button
          style={{ ...(format === "single_image" ? primaryButtonStyle : secondaryButtonStyle), flex: 1 }}
          onClick={() => setFormat("single_image")}
        >
          Single image
        </button>
      </section>

      {format === "single_image" && (
        <section style={{ display: "flex", gap: 8 }}>
          <button
            style={{
              ...(singleImageStyle === "quote" ? primaryButtonStyle : secondaryButtonStyle),
              flex: 1,
            }}
            onClick={() => setSingleImageStyle("quote")}
          >
            Poetic Quote
          </button>
          <button
            style={{
              ...(singleImageStyle === "stat" ? primaryButtonStyle : secondaryButtonStyle),
              flex: 1,
            }}
            onClick={() => setSingleImageStyle("stat")}
          >
            Quick Stat
          </button>
        </section>
      )}

      {error && <ErrorBanner message={error} />}

      {format === "single_image" && proposing && <p style={{ opacity: 0.6 }}>Thinking of an angle…</p>}

      {format === "single_image" && proposal && !proposing && (
        <section style={cardStyle}>
          <div style={labelStyle}>AI proposes</div>
          <div style={{ fontSize: 19, fontWeight: 700 }}>
            {APPROACH_LABELS[proposal.approach] ?? proposal.approach}
          </div>
          <div style={{ fontSize: 15, lineHeight: 1.4 }}>{proposal.angle}</div>
          <div style={{ fontSize: 13, opacity: 0.65, fontStyle: "italic" }}>{proposal.reason}</div>

          <button
            style={{ ...secondaryButtonStyle, marginTop: 12 }}
            onClick={() => void loadProposal()}
            disabled={generating}
          >
            Try another angle
          </button>
          <button
            style={{ ...primaryButtonStyle, opacity: generating ? 0.6 : 1 }}
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? "Generating…" : "Generate"}
          </button>
        </section>
      )}

      {format === "carousel" && (
        <section style={cardStyle}>
          <div style={labelStyle}>Ready to generate</div>
          <div style={{ fontSize: 15, lineHeight: 1.4, opacity: 0.75 }}>
            This picks its own anchor and writes the full carousel in one pass —
            there&rsquo;s no angle preview to accept first.
          </div>

          <button
            style={{ ...primaryButtonStyle, marginTop: 12, opacity: generating ? 0.6 : 1 }}
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? "Generating…" : "Generate"}
          </button>

          {generating && (
            <p style={{ fontSize: 13, opacity: 0.65, marginTop: 8 }}>
              {carouselWaitMessage(elapsedSeconds)}
            </p>
          )}
        </section>
      )}
    </main>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      style={{
        background: "#FCE9E7",
        color: "#8C3B2E",
        borderRadius: 10,
        padding: "10px 14px",
        fontSize: 14,
      }}
    >
      {message}
    </div>
  );
}
