"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { generatePost, proposeApproach } from "@/lib/api";
import type { ApiFormat, ProposeResponse } from "@/lib/api-types";
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
  const [proposal, setProposal] = useState<ProposeResponse | null>(null);
  const [proposing, setProposing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!topicId) return;
    void loadProposal();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topicId, format]);

  async function loadProposal() {
    if (!topicId) return;
    setProposing(true);
    setError(null);
    try {
      setProposal(await proposeApproach(topicId, format));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setProposing(false);
    }
  }

  async function handleGenerate() {
    if (!topicId || !proposal) return;
    setGenerating(true);
    setError(null);
    try {
      const generated = await generatePost(topicId, format, {
        angle: proposal.angle,
        approach: proposal.approach,
        mood: proposal.mood,
        visual_subject: proposal.visual_subject,
        fingerprint: proposal.fingerprint,
      });
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

  return (
    <main style={screenStyle}>
      <header>
        <button style={ghostButtonStyle} onClick={() => router.push("/")}>
          ← Back
        </button>
        <h1 style={{ fontSize: 22, marginTop: 8 }}>{proposal?.topic_name ?? "Loading…"}</h1>
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

      {error && <ErrorBanner message={error} />}

      {proposing && <p style={{ opacity: 0.6 }}>Thinking of an angle…</p>}

      {proposal && !proposing && (
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
