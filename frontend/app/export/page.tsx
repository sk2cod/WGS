"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
    rendered.forEach((slide, i) => {
      setTimeout(() => downloadBlobUrl(slide.url, slide.filename), i * 300);
    });
  }

  function handleDone() {
    clearCurrentPost();
    router.push("/");
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

      <button style={ghostButtonStyle} onClick={handleDone}>
        Done — back to home
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
