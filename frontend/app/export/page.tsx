"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { confirmExport } from "@/lib/api";
import type { GenerateResponse } from "@/lib/api-types";
import { resolveTokens } from "@/lib/brand-tokens";
import { parseMasthead } from "@/lib/masthead";
import { clearCurrentPost, loadCurrentPost } from "@/lib/session-store";
import { renderSlideToBlob } from "@/lib/render-client";
import { WGS_BRAND_KIT } from "@/lib/wgs-brand-kit";
import {
  cardStyle,
  ghostButtonStyle,
  labelStyle,
  primaryButtonStyle,
  screenStyle,
  secondaryButtonStyle,
} from "@/lib/ui-styles";

interface RenderedSlide {
  url: string;
  filename: string;
}

function downloadBlobUrl(url: string, filename: string) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export default function ExportPage() {
  const router = useRouter();
  const [data, setData] = useState<GenerateResponse | null>(null);
  const [rendered, setRendered] = useState<RenderedSlide[] | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  // Tracks that "Save images" was actually invoked — same standard as `copied`
  // above, just without the 2s auto-revert (that part is copied's button-label
  // behavior specifically, not a general pattern this needs).
  const [savedImages, setSavedImages] = useState(false);
  // Defaults off; auto-flips true the first time handleDownloadAll() fires (a real
  // save, not just viewing the preview) and never auto-reverts after that — she can
  // still manually turn it back off, and a second "Save images" tap won't re-force
  // it back on if she did.
  const [trainVoice, setTrainVoice] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  // Set only when train_voice was true and voice_training_status comes back
  // "failed" — a brief, non-blocking heads-up before navigating home as normal.
  // Not a recovery flow: no retry button, nothing persisted here; the failure is
  // already logged server-side (routes/export.py) for manual replay if it matters.
  const [doneNotice, setDoneNotice] = useState<string | null>(null);

  // sessionStorage isn't available during SSR, so the initial data load must happen
  // client-side in an effect (not a lazy useState initializer) — otherwise the
  // server-rendered "Loading…" markup mismatches the client's first real render.
  useEffect(() => {
    const loaded = loadCurrentPost();
    if (!loaded) {
      router.replace("/");
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setData(loaded);
  }, [router]);

  useEffect(() => {
    if (!data) return;
    let cancelled = false;

    async function renderAll() {
      try {
        const tokens = resolveTokens(WGS_BRAND_KIT, data!.brief.mood);
        const masthead = parseMasthead(data!.masthead);
        const heroUrl = data!.hero_image_base64 ? `data:image/png;base64,${data!.hero_image_base64}` : null;

        const results: RenderedSlide[] = [];
        for (let i = 0; i < data!.post.slides.length; i++) {
          const blob = await renderSlideToBlob(data!.post.slides[i], masthead, tokens, heroUrl);
          results.push({
            url: URL.createObjectURL(blob),
            filename: `wgs-${data!.brief.topic_id}-slide-${i + 1}.png`,
          });
        }
        if (!cancelled) setRendered(results);
      } catch (err) {
        if (!cancelled) setRenderError(err instanceof Error ? err.message : String(err));
      }
    }

    void renderAll();
    return () => {
      cancelled = true;
    };
  }, [data]);

  async function handleCopyCaption() {
    if (!data) return;
    const text = [data.post.caption, data.post.hashtags.join(" ")].filter(Boolean).join("\n\n");
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownloadAll() {
    if (!rendered) return;
    if (!savedImages) {
      setTrainVoice(true);
    }
    setSavedImages(true);
    rendered.forEach((slide, i) => {
      setTimeout(() => downloadBlobUrl(slide.url, slide.filename), i * 300);
    });
  }

  async function handleDone() {
    if (!data) return;
    setConfirming(true);
    setConfirmError(null);
    try {
      const result = await confirmExport(data.memory_id, data.post.caption, data.post.slides, trainVoice);
      if (trainVoice && result.voice_training_status === "failed") {
        // The export itself succeeded — nothing here should block getting back home,
        // just make the training miss visible before she leaves the screen.
        setDoneNotice("Exported! (Voice training didn't complete this time — no action needed.)");
        setTimeout(() => {
          clearCurrentPost();
          router.push("/");
        }, 2500);
        return;
      }
      clearCurrentPost();
      router.push("/");
    } catch (err) {
      setConfirmError(err instanceof Error ? err.message : String(err));
    } finally {
      setConfirming(false);
    }
  }

  if (!data) {
    return (
      <main style={screenStyle}>
        <p style={{ opacity: 0.6 }}>Loading…</p>
      </main>
    );
  }

  return (
    <main style={screenStyle}>
      <header>
        <button style={ghostButtonStyle} onClick={() => router.push("/editor")}>
          ← Back to editor
        </button>
        <h1 style={{ fontSize: 22, marginTop: 8 }}>Export</h1>
        <div style={labelStyle}>{data.masthead}</div>
      </header>

      {renderError && <ErrorBanner message={renderError} />}
      {!rendered && !renderError && <p style={{ opacity: 0.6 }}>Rendering final images…</p>}

      {rendered && (
        <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))",
              gap: 10,
            }}
          >
            {rendered.map((slide, i) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                key={i}
                src={slide.url}
                alt={`Slide ${i + 1}`}
                style={{ width: "100%", borderRadius: 10, aspectRatio: "4/5", objectFit: "cover" }}
                onClick={() => downloadBlobUrl(slide.url, slide.filename)}
              />
            ))}
          </div>
          <button style={primaryButtonStyle} onClick={handleDownloadAll}>
            Save images
          </button>
          <p style={{ fontSize: 12, opacity: 0.55, textAlign: "center", marginTop: -8 }}>
            Tap an image to save it individually, or use Save images for all of them.
          </p>
        </section>
      )}

      <section style={cardStyle}>
        <div style={labelStyle}>Caption + hashtags</div>
        <p style={{ fontSize: 14, whiteSpace: "pre-wrap" }}>{data.post.caption}</p>
        <p style={{ fontSize: 14, opacity: 0.7 }}>{data.post.hashtags.join(" ")}</p>
        <button style={secondaryButtonStyle} onClick={handleCopyCaption}>
          {copied ? "Copied ✓" : "Copy caption + hashtags"}
        </button>
      </section>

      <p style={{ fontSize: 13, opacity: 0.6, textAlign: "center" }}>
        Save the images and copy the caption, then post from the Instagram app.
      </p>

      <label style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, padding: "4px 2px" }}>
        <input
          type="checkbox"
          checked={trainVoice}
          onChange={(e) => setTrainVoice(e.target.checked)}
        />
        Use this post to improve future writing
      </label>

      {confirmError && <ErrorBanner message={confirmError} />}
      {doneNotice && (
        <p style={{ fontSize: 13, opacity: 0.75, textAlign: "center" }}>{doneNotice}</p>
      )}

      <button style={ghostButtonStyle} onClick={handleDone} disabled={confirming}>
        {confirming ? "Saving…" : "Done — back to home"}
      </button>
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
