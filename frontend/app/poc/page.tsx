"use client";

import { useEffect, useState } from "react";
import { getTopics } from "@/lib/api";
import type { Topic } from "@/lib/api-types";
import { resolveTokens } from "@/lib/brand-tokens";
import { WGS_BRAND_KIT } from "@/lib/wgs-brand-kit";
import { generatePoc, PocApiError } from "@/lib/poc-api";
import type { PocGenerateResponse } from "@/lib/poc-types";
import PocParagraphSlide from "@/components/slides/PocParagraphSlide";
import ScaledSlide from "@/components/ui/ScaledSlide";
import {
  cardStyle,
  inputStyle,
  labelStyle,
  primaryButtonStyle,
  screenStyle,
} from "@/lib/ui-styles";

// Isolated POC page — hits POST /poc/generate only, never the real /generate
// pipeline. Fixed mood (no angle engine here to tag one) is fine for a POC;
// masthead is fixed to just the brand short name, matching how Masthead.tsx
// renders everywhere else in the app.
const POC_MASTHEAD = { masthead_short: WGS_BRAND_KIT.masthead_short, category: "", number: "" };
const POC_TOKENS = resolveTokens(WGS_BRAND_KIT, "wisdom");
const SCALE = 0.32;

export default function PocPage() {
  const [topics, setTopics] = useState<Topic[] | null>(null);
  const [selectedTopicId, setSelectedTopicId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PocGenerateResponse | null>(null);

  useEffect(() => {
    getTopics()
      .then((t) => {
        setTopics(t);
        if (t.length > 0) setSelectedTopicId(t[0].id);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  async function handleGenerate() {
    if (!selectedTopicId) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await generatePoc(selectedTopicId));
    } catch (err) {
      setError(
        err instanceof PocApiError
          ? `${err.status}: ${err.message}`
          : err instanceof Error
            ? err.message
            : String(err),
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={screenStyle}>
      <header>
        <div style={labelStyle}>POC — isolated experiment</div>
        <h1 style={{ fontSize: 26, marginTop: 4 }}>Micro-essay writer</h1>
        <p style={{ fontSize: 14, opacity: 0.7, marginTop: 4 }}>
          One Sonnet call, no sampling, no critique/refine. Separate from the real
          Carousel/Single Image pipeline entirely.
        </p>
      </header>

      <section style={cardStyle}>
        <div style={labelStyle}>Topic</div>
        {!topics && !error && <p style={{ opacity: 0.6 }}>Loading topics…</p>}
        {topics && (
          <select
            style={inputStyle}
            value={selectedTopicId}
            onChange={(e) => setSelectedTopicId(e.target.value)}
            disabled={loading}
          >
            {topics.map((t) => (
              <option key={t.id} value={t.id}>
                {t.primary_category} — {t.name}
              </option>
            ))}
          </select>
        )}
        <button
          style={{ ...primaryButtonStyle, opacity: loading || !selectedTopicId ? 0.6 : 1 }}
          onClick={handleGenerate}
          disabled={loading || !selectedTopicId}
        >
          {loading ? "Writing…" : "Generate POC"}
        </button>
        {error && <ErrorBanner message={error} />}
      </section>

      {result && (
        <>
          <section
            style={{
              display: "flex",
              gap: 16,
              overflowX: "auto",
              paddingBottom: 8,
            }}
          >
            {result.slides.map((text, i) => (
              <ScaledSlide key={i} scale={SCALE}>
                <PocParagraphSlide text={text} masthead={POC_MASTHEAD} tokens={POC_TOKENS} />
              </ScaledSlide>
            ))}
          </section>

          <section style={cardStyle}>
            <div style={labelStyle}>Conversation question</div>
            <p style={{ fontSize: 15, lineHeight: 1.5 }}>{result.conversation_question}</p>
          </section>

          <section style={cardStyle}>
            <div style={labelStyle}>Caption</div>
            <p style={{ fontSize: 15, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{result.caption}</p>
          </section>
        </>
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
