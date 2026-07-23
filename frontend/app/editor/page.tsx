"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { regenerateSlide, reshuffleImage } from "@/lib/api";
import type { ApiSlide, GenerateResponse } from "@/lib/api-types";
import { resolveTokens } from "@/lib/brand-tokens";
import { parseMasthead } from "@/lib/masthead";
import { clearCurrentPost, loadCurrentPost, saveCurrentPost } from "@/lib/session-store";
import { WGS_BRAND_KIT } from "@/lib/wgs-brand-kit";
import { CANVAS_HEIGHT, CANVAS_WIDTH } from "@/lib/canvas";
import SlideRenderer from "@/components/ui/SlideRenderer";
import {
  cardStyle,
  ghostButtonStyle,
  inputStyle,
  labelStyle,
  primaryButtonStyle,
  screenStyle,
  secondaryButtonStyle,
} from "@/lib/ui-styles";

const PREVIEW_SCALE = 0.32;

export default function EditorPage() {
  const router = useRouter();
  const [data, setData] = useState<GenerateResponse | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [regenerating, setRegenerating] = useState(false);
  const [reshuffling, setReshuffling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const heroVariant = useRef(1);
  const scrollRef = useRef<HTMLDivElement>(null);

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

  if (!data) {
    return (
      <main style={screenStyle}>
        <p style={{ opacity: 0.6 }}>Loading…</p>
      </main>
    );
  }

  const tokens = resolveTokens(WGS_BRAND_KIT, data.brief.mood);
  const masthead = parseMasthead(data.masthead);
  const slides = data.post.slides;
  const activeSlide = slides[activeIndex];
  const slideWidth = CANVAS_WIDTH * PREVIEW_SCALE;

  function goToSlide(index: number) {
    setActiveIndex(index);
    scrollRef.current?.scrollTo({ left: index * (slideWidth + 12), behavior: "smooth" });
  }

  function handleScroll() {
    const el = scrollRef.current;
    if (!el) return;
    const index = Math.round(el.scrollLeft / (slideWidth + 12));
    if (index !== activeIndex && index >= 0 && index < slides.length) {
      setActiveIndex(index);
    }
  }

  function updateSlide(index: number, patch: Partial<ApiSlide>) {
    setData((prev) => {
      if (!prev) return prev;
      const nextSlides = prev.post.slides.map((s, i) =>
        i === index ? ({ ...s, ...patch } as ApiSlide) : s,
      );
      return { ...prev, post: { ...prev.post, slides: nextSlides } };
    });
  }

  async function handleRegenerateSlide() {
    if (!data) return;
    setRegenerating(true);
    setError(null);
    try {
      const { slide } = await regenerateSlide(data.brief, data.post, activeIndex);
      setData((prev) => {
        if (!prev) return prev;
        const nextSlides = prev.post.slides.map((s, i) => (i === activeIndex ? slide : s));
        return { ...prev, post: { ...prev.post, slides: nextSlides } };
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRegenerating(false);
    }
  }

  async function handleReshuffleImage() {
    if (!data) return;
    setReshuffling(true);
    setError(null);
    try {
      heroVariant.current += 1;
      const { hero_image_base64 } = await reshuffleImage(data.brief, heroVariant.current);
      setData((prev) => (prev ? { ...prev, hero_image_base64 } : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setReshuffling(false);
    }
  }

  function handleContinue() {
    if (!data) return;
    saveCurrentPost(data);
    router.push("/export");
  }

  function handleStartOver() {
    clearCurrentPost();
    router.push("/");
  }

  return (
    <main style={screenStyle}>
      <header>
        <button style={ghostButtonStyle} onClick={handleStartOver}>
          ✕ Start over
        </button>
        <div style={{ ...labelStyle, marginTop: 8 }}>{data.masthead}</div>
      </header>

      {error && <ErrorBanner message={error} />}
      {data.validation_errors.length > 0 && (
        <ErrorBanner message={`Needs a look: ${data.validation_errors.join("; ")}`} />
      )}

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        style={{
          display: "flex",
          gap: 12,
          overflowX: "auto",
          scrollSnapType: "x mandatory",
          paddingBottom: 8,
        }}
      >
        {slides.map((slide, i) => (
          <div
            key={i}
            style={{
              flex: "0 0 auto",
              scrollSnapAlign: "center",
              width: slideWidth,
              height: CANVAS_HEIGHT * PREVIEW_SCALE,
              overflow: "hidden",
              borderRadius: 12,
              boxShadow: "0 2px 10px rgba(0,0,0,0.15)",
            }}
          >
            <div
              style={{
                width: CANVAS_WIDTH,
                height: CANVAS_HEIGHT,
                transform: `scale(${PREVIEW_SCALE})`,
                transformOrigin: "top left",
              }}
            >
              <SlideRenderer
                slide={slide}
                masthead={masthead}
                tokens={tokens}
                heroImageUrl={
                  data.hero_image_base64 ? `data:image/png;base64,${data.hero_image_base64}` : null
                }
              />
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", justifyContent: "center", gap: 8 }}>
        {slides.map((_, i) => (
          <button
            key={i}
            onClick={() => goToSlide(i)}
            aria-label={`Slide ${i + 1}`}
            style={{
              width: 8,
              height: 8,
              borderRadius: 999,
              border: "none",
              padding: 0,
              background: i === activeIndex ? WGS_BRAND_KIT.mood_palettes[data.brief.mood].accent : "#ddd",
            }}
          />
        ))}
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <button
          style={{ ...secondaryButtonStyle, flex: 1, opacity: regenerating ? 0.6 : 1 }}
          onClick={handleRegenerateSlide}
          disabled={regenerating}
        >
          {regenerating ? "Rewriting…" : "Regenerate this slide"}
        </button>
        {activeSlide.template_id === "carousel_cover" && (
          <button
            style={{ ...secondaryButtonStyle, flex: 1, opacity: reshuffling ? 0.6 : 1 }}
            onClick={handleReshuffleImage}
            disabled={reshuffling}
          >
            {reshuffling ? "Reshuffling…" : "Reshuffle image"}
          </button>
        )}
      </div>

      <SlideEditForm slide={activeSlide} onChange={(patch) => updateSlide(activeIndex, patch)} />

      <section style={cardStyle}>
        <div style={labelStyle}>Caption</div>
        <textarea
          style={{ ...inputStyle, minHeight: 90, resize: "vertical" }}
          value={data.post.caption}
          onChange={(e) =>
            setData((prev) => (prev ? { ...prev, post: { ...prev.post, caption: e.target.value } } : prev))
          }
        />
        <div style={labelStyle}>Hashtags</div>
        <input
          style={inputStyle}
          value={data.post.hashtags.join(" ")}
          onChange={(e) =>
            setData((prev) =>
              prev
                ? { ...prev, post: { ...prev.post, hashtags: e.target.value.split(/\s+/).filter(Boolean) } }
                : prev,
            )
          }
        />
      </section>

      <button style={primaryButtonStyle} onClick={handleContinue}>
        Continue to export
      </button>
    </main>
  );
}

function SlideEditForm({
  slide,
  onChange,
}: {
  slide: ApiSlide;
  onChange: (patch: Partial<ApiSlide>) => void;
}) {
  switch (slide.template_id) {
    case "carousel_cover":
      return (
        <section style={cardStyle}>
          <div style={labelStyle}>Edit this slide</div>
          <Field label="Headline" value={slide.headline_word} onChange={(v) => onChange({ headline_word: v })} />
          <Field label="Script phrase" value={slide.script_word} onChange={(v) => onChange({ script_word: v })} />
          <Field label="Kicker" value={slide.kicker} onChange={(v) => onChange({ kicker: v })} />
          {/* cover_body: the carousel direct-write port's field (task "#19") --
              only ever populated on that path, so shown unconditionally is fine
              (legacy leaves it empty and this field simply stays blank). */}
          <Field
            label="Cover body"
            value={slide.cover_body ?? ""}
            onChange={(v) => onChange({ cover_body: v })}
            multiline
          />
        </section>
      );
    case "carousel_body":
      return (
        <section style={cardStyle}>
          <div style={labelStyle}>Edit this slide</div>
          <Field
            label="Before the emphasis"
            value={slide.statement_pre}
            onChange={(v) => onChange({ statement_pre: v })}
          />
          <Field
            label="Emphasized phrase"
            value={slide.statement_script}
            onChange={(v) => onChange({ statement_script: v })}
          />
          <Field
            label="After the emphasis"
            value={slide.statement_post}
            onChange={(v) => onChange({ statement_post: v })}
          />
        </section>
      );
    case "carousel_closing":
      return (
        <section style={cardStyle}>
          <div style={labelStyle}>Edit this slide</div>
          <Field label="Takeaway" value={slide.takeaway} onChange={(v) => onChange({ takeaway: v })} />
        </section>
      );
    case "carousel_conversation":
      // label, invite, cta, and handle are all fixed brand copy (same pattern
      // as carousel_closing's signature) — only question is ever editable here.
      return (
        <section style={cardStyle}>
          <div style={labelStyle}>Edit this slide</div>
          <Field label="Question" value={slide.question} onChange={(v) => onChange({ question: v })} multiline />
        </section>
      );
    case "single_quote":
      return (
        <section style={cardStyle}>
          <div style={labelStyle}>Edit this slide</div>
          <Field label="Quote" value={slide.quote} onChange={(v) => onChange({ quote: v })} multiline />
        </section>
      );
    case "single_stat":
      return (
        <section style={cardStyle}>
          <div style={labelStyle}>Edit this slide</div>
          <Field label="Kicker" value={slide.kicker} onChange={(v) => onChange({ kicker: v })} />
          <Field label="Number" value={slide.number} onChange={(v) => onChange({ number: v })} />
          <Field
            label="Supporting line"
            value={slide.supporting_line}
            onChange={(v) => onChange({ supporting_line: v })}
          />
        </section>
      );
  }
}

function Field({
  label,
  value,
  onChange,
  multiline,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
}) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{ fontSize: 12, opacity: 0.6 }}>{label}</span>
      {multiline ? (
        <textarea
          style={{ ...inputStyle, minHeight: 70, resize: "vertical" }}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input style={inputStyle} value={value} onChange={(e) => onChange(e.target.value)} />
      )}
    </label>
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
