"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ApiError, generateFromBrief, getDailyPicks, getTopics, pasteLink, rerollPick } from "@/lib/api";
import type { DailyPick, DailyPicksResult, Topic } from "@/lib/api-types";
import { saveCurrentPost } from "@/lib/session-store";
import {
  cardStyle,
  colors,
  ghostButtonStyle,
  inputStyle,
  labelStyle,
  primaryButtonStyle,
  screenStyle,
  secondaryButtonStyle,
} from "@/lib/ui-styles";

export default function Home() {
  const router = useRouter();
  const [picks, setPicks] = useState<DailyPicksResult | null>(null);
  const [picksError, setPicksError] = useState<string | null>(null);
  const [rerollingIndex, setRerollingIndex] = useState<number | null>(null);

  const [browsing, setBrowsing] = useState(false);
  const [topics, setTopics] = useState<Topic[] | null>(null);

  const [pasteUrl, setPasteUrl] = useState("");
  const [pasting, setPasting] = useState(false);
  const [pasteError, setPasteError] = useState<string | null>(null);

  useEffect(() => {
    getDailyPicks()
      .then(setPicks)
      .catch((err) => setPicksError(err instanceof Error ? err.message : String(err)));
  }, []);

  async function handleReroll(index: number) {
    setRerollingIndex(index);
    try {
      const updated = await rerollPick(index);
      setPicks(updated);
    } catch (err) {
      setPicksError(err instanceof Error ? err.message : String(err));
    } finally {
      setRerollingIndex(null);
    }
  }

  async function handleBrowseToggle() {
    setBrowsing((prev) => !prev);
    if (!topics) {
      try {
        setTopics(await getTopics());
      } catch (err) {
        setPicksError(err instanceof Error ? err.message : String(err));
      }
    }
  }

  function goToGenerate(topicId: string) {
    router.push(`/generate?topic_id=${encodeURIComponent(topicId)}`);
  }

  async function handlePasteSubmit() {
    if (!pasteUrl.trim()) return;
    setPasting(true);
    setPasteError(null);
    try {
      const { brief, masthead } = await pasteLink(pasteUrl.trim(), "carousel");
      const generated = await generateFromBrief(brief, masthead);
      saveCurrentPost(generated);
      router.push("/editor");
    } catch (err) {
      setPasteError(
        err instanceof ApiError
          ? "Couldn't read that article — try a different link."
          : err instanceof Error
            ? err.message
            : String(err),
      );
    } finally {
      setPasting(false);
    }
  }

  return (
    <main style={screenStyle}>
      <header>
        <div style={labelStyle}>{"Women's Growth Society"}</div>
        <h1 style={{ fontSize: 26, marginTop: 4 }}>What should we make today?</h1>
      </header>

      {picksError && <ErrorBanner message={picksError} />}

      {!picks && !picksError && <p style={{ opacity: 0.6 }}>Loading today&rsquo;s picks…</p>}

      {picks && picks.picks.length > 0 && (
        <>
          <TodaysPick pick={picks.picks[0]} onCreate={() => goToGenerate(picks.picks[0].topic_id)} />

          <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={labelStyle}>More today</div>
            {picks.picks.slice(1).map((pick, i) => (
              <PickCard
                key={`${pick.topic_id}-${i}`}
                pick={pick}
                rerolling={rerollingIndex === i + 1}
                onCreate={() => goToGenerate(pick.topic_id)}
                onReroll={() => handleReroll(i + 1)}
              />
            ))}
          </section>
        </>
      )}

      <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <button style={ghostButtonStyle} onClick={handleBrowseToggle}>
          {browsing ? "Hide full topic list ▲" : "Browse all topics ▼"}
        </button>
        {browsing && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {!topics && <p style={{ opacity: 0.6 }}>Loading topics…</p>}
            {topics?.map((topic) => (
              <button
                key={topic.id}
                onClick={() => goToGenerate(topic.id)}
                style={{
                  ...cardStyle,
                  padding: "12px 16px",
                  textAlign: "left",
                  cursor: "pointer",
                }}
              >
                <span style={{ fontWeight: 600 }}>{topic.name}</span>
                <span style={{ fontSize: 13, opacity: 0.6 }}>{topic.primary_category}</span>
              </button>
            ))}
          </div>
        )}
      </section>

      <section style={cardStyle}>
        <div style={labelStyle}>Paste a link</div>
        <p style={{ fontSize: 14, opacity: 0.75, marginTop: -4 }}>
          Turn a news article into an attributed post.
        </p>
        <input
          style={inputStyle}
          type="url"
          placeholder="https://…"
          value={pasteUrl}
          onChange={(e) => setPasteUrl(e.target.value)}
          disabled={pasting}
        />
        {pasteError && <ErrorBanner message={pasteError} />}
        <button
          style={{ ...secondaryButtonStyle, opacity: pasting ? 0.6 : 1 }}
          onClick={handlePasteSubmit}
          disabled={pasting || !pasteUrl.trim()}
        >
          {pasting ? "Reading article…" : "Create from this link"}
        </button>
      </section>

      <Link href="/preview" style={{ ...labelStyle, textAlign: "center" }}>
        View template preview grid
      </Link>
    </main>
  );
}

function TodaysPick({ pick, onCreate }: { pick: DailyPick; onCreate: () => void }) {
  return (
    <section style={{ ...cardStyle, background: colors.primary, color: "#fff", border: "none" }}>
      <div style={{ ...labelStyle, color: "#fff", opacity: 0.75 }}>
        {"Today's pick"} · {pick.category}
        {pick.source_type === "timely" && pick.awareness_day_name ? ` · ${pick.awareness_day_name}` : ""}
      </div>
      <div style={{ fontSize: 21, fontWeight: 700, lineHeight: 1.3 }}>{pick.hook}</div>
      <button
        style={{ ...primaryButtonStyle, background: "#fff", color: colors.primary, marginTop: 8 }}
        onClick={onCreate}
      >
        Create this
      </button>
    </section>
  );
}

function PickCard({
  pick,
  rerolling,
  onCreate,
  onReroll,
}: {
  pick: DailyPick;
  rerolling: boolean;
  onCreate: () => void;
  onReroll: () => void;
}) {
  return (
    <div style={cardStyle}>
      <div style={labelStyle}>
        {pick.category}
        {pick.source_type === "timely" ? " · timely" : ""}
      </div>
      <div style={{ fontSize: 17, fontWeight: 600, lineHeight: 1.35 }}>{pick.hook}</div>
      <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
        <button style={{ ...primaryButtonStyle, flex: 1, padding: "10px 16px" }} onClick={onCreate}>
          Create
        </button>
        <button
          style={{ ...secondaryButtonStyle, padding: "10px 16px", opacity: rerolling ? 0.6 : 1 }}
          onClick={onReroll}
          disabled={rerolling}
        >
          {rerolling ? "…" : "Reroll"}
        </button>
      </div>
    </div>
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
