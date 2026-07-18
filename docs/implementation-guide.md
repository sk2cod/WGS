# Implementation Guide — AI Content Studio

**Companion to:** `content-studio-blueprint-final.md` (the design reference — read it first)
**Purpose:** hand this to Claude Code and build Phase 1 in the order below. Each phase has a goal, the files to create, acceptance criteria, and a ready-to-paste Claude Code prompt.
**Runtime targets:** Python 3.11 · Node 20+ · single-creator · quality-first, cost-controlled.

---

## 0. How to use this document

Build **in phase order** — each phase depends on the one before it. Don't skip ahead; the design foundation (Phase 1) exists to prove the quality ceiling before any AI is wired in, and later phases assume the contracts from earlier ones exist.

For each phase: paste the "Claude Code prompt" block, let it scaffold, then check the "Done when" criteria before moving on. The Pydantic contracts in Section 6 are the source of truth — everything reads and writes those shapes.

### Phase gating — stop, verify, wait

Every phase prompt below ends with the same standing instruction, so it's stated once here rather than repeated six times:

> **After finishing this phase, invoke the `phase-verifier` subagent (defined below) against this phase's "Done when" criteria. Report its findings — pass/fail per criterion, with evidence (file paths, command output, not just assertion). Then STOP. Do not begin the next phase, even if verification passes, until I explicitly confirm.**

This uses Claude Code's native **subagent** feature — a separate, isolated context window the main session can spawn for a bounded task, returning only a summary — not the heavier "agent teams" feature (multiple coordinating sessions), which costs roughly 3-4x the tokens for coordination overhead that this project's sequential, non-parallel phases don't benefit from. A subagent is the right-sized tool here: cheap, built-in, and — because it runs in its own context rather than the one that just wrote the code — a genuinely independent check rather than the implementer grading its own homework.

**One-time setup, before Phase 1:** have Claude Code create this file first:

`.claude/agents/phase-verifier.md`:
```markdown
---
name: phase-verifier
description: Independently verifies a completed phase against its Done-when criteria. Read-only.
tools: Read, Grep, Glob, Bash
---
You are a verification specialist, not an implementer. You did not write the code you are
checking, and you should evaluate it skeptically rather than assume it works.

Given a numbered list of "Done when" criteria for a phase, check each one against the actual
repository state — read the files, run any relevant commands (tests, type-checks, the preview
page's build), and report PASS or FAIL per criterion with concrete evidence (a file path and
line, or command output). Never mark something PASS on the basis of a file merely existing —
confirm it does what the criterion requires.

Do not modify any files. If something fails, describe exactly what's missing or wrong, precisely
enough that the main session can fix it without re-investigating from scratch.
```

---

## 1. Locked stack & decisions

| Concern | Decision |
|---|---|
| Cheap/fast text | Claude Haiku 4.5 — `claude-haiku-4-5-20251001` |
| Strong text | Claude Sonnet 5 — `claude-sonnet-5` |
| Image generation | GPT Image 2 — `gpt-image-2`, portrait 1024×1536, quality flag (start `medium`, test `low`) |
| Duotone | Pillow, deterministic, in-backend (free) |
| Render | Satori via `@vercel/og`, as a Next.js route (no headless browser) |
| Frontend | Next.js (App Router) + pnpm, hosted on Vercel |
| Backend | FastAPI + `uv`, Python 3.11, hosted on Railway |
| Data + storage + auth | Supabase (Postgres + Storage + Auth) |
| Repo | One monorepo, two deploy configs |
| Contracts | Pydantic v2 |

**Why Satori lives on the frontend:** Satori is a JavaScript library, so rather than run Node inside the Python backend, rendering is a Vercel route. The backend produces *slide content + a duotoned hero image URL*; the frontend's render route rasterizes to PNG. Backend stays pure Python; rendering stays where Satori is native. The render contract (Section 8) is unchanged — only its host is the frontend.

---

## 2. Accounts & subscriptions checklist

All pay-as-you-go or free tier — no fixed subscriptions required for Phase 1.

| Service | Plan for Phase 1 | What you need from it |
|---|---|---|
| Anthropic (platform.claude.com) | Pay-as-you-go API ($5 free credit to start) | `ANTHROPIC_API_KEY` |
| OpenAI (platform.openai.com) | Pay-as-you-go API ($5 free credit to start) | `OPENAI_API_KEY` |
| Supabase | Free tier | Project URL, `anon` key, `service_role` key, Postgres connection string |
| GitHub | Free | One repo (source of truth, triggers deploys) |
| Vercel | Hobby (free) | Connect the repo; hosts `frontend/` |
| Railway | ~$5/mo starter (or Render free w/ cold starts) | Connect the repo; hosts `backend/`; gives the public API URL |
| Custom domain | Optional (~$12/yr) | `api.yourbrand.com` CNAME — not required for launch |

**Estimated running cost at 6 posts/day:** ~$15–27/month (API + backend host), dropping to ~$10–15 if the image quality flag is set to `low` after the duotone test. See blueprint cost section.

---

## 3. Prerequisites (local machine)

```bash
python --version        # 3.11.x  (already installed)
node --version          # 20+
pip install uv          # fast Python package/dep manager
npm install -g pnpm      # frontend package manager
```

---

## 4. Folder structure (monorepo)

```
content-studio/
├── README.md
├── .gitignore
├── .env.example                    # template — never commit real .env
├── docs/
│   └── blueprint.md                # the frozen design reference
│
├── frontend/                       # Next.js — deploys to Vercel
│   ├── package.json
│   ├── next.config.js
│   ├── .env.local.example
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                # Home: today's pick + 3 daily picks
│   │   ├── onboarding/page.tsx     # Brand Kit capture
│   │   ├── generate/page.tsx       # topic + format → generate
│   │   ├── editor/page.tsx         # swipe-edit, per-slide regenerate
│   │   ├── export/page.tsx         # save to camera roll + copy caption
│   │   └── api/
│   │       └── render/route.ts     # Satori (@vercel/og) → PNG  [the render contract]
│   ├── components/
│   │   ├── slides/                 # JSX slide templates (live-preview + Satori)
│   │   │   ├── Masthead.tsx         # shared: {masthead_short} — rule — {category} NO. {n}
│   │   │   ├── CarouselCover.tsx    # has photo — the only template that does
│   │   │   ├── CarouselBody.tsx
│   │   │   ├── CarouselClosing.tsx  # masthead top; takeaway→signature→CTA→tiny handle footnote, centered in flex:1 below
│   │   │   ├── SingleQuote.tsx
│   │   │   └── SingleStat.tsx
│   │   └── ui/
│   ├── lib/
│   │   ├── api.ts                  # calls NEXT_PUBLIC_API_URL
│   │   └── brand-tokens.ts         # reads BrandKit → CSS vars
│   └── styles/
│
├── backend/                        # FastAPI — deploys to Railway
│   ├── pyproject.toml
│   ├── .env.example
│   ├── app/
│   │   ├── main.py                 # FastAPI entry + CORS (restrict to Vercel domain)
│   │   ├── config.py               # settings, env vars, COST FLAGS
│   │   ├── models/                 # Pydantic contracts (Section 6)
│   │   │   ├── enums.py
│   │   │   ├── brand_kit.py
│   │   │   ├── topic.py
│   │   │   ├── brief.py
│   │   │   └── memory.py
│   │   ├── taxonomy/
│   │   │   ├── topics.yaml          # 40–60 authored topics
│   │   │   ├── approaches.py        # ~8 global approaches
│   │   │   ├── entry_points.py      # ~5 global entry points
│   │   │   └── voice_register.py    # approach → voice register ("poetic" | "direct") lookup
│   │   ├── engine/
│   │   │   ├── selector.py          # daily picks (coverage-aware, date-seeded)
│   │   │   ├── angle_engine.py      # samples one cell, avoids recent combos
│   │   │   ├── brief_builder.py     # assembles ContentBrief
│   │   │   ├── generator.py         # draft → critique → refine (text)
│   │   │   ├── validator.py         # brand, safety, citations, repetition
│   │   │   └── memory.py            # read/write MemoryRecord + voice store
│   │   ├── providers/
│   │   │   ├── llm.py               # tiered LLM adapter (Haiku / Sonnet)
│   │   │   ├── image.py             # image adapter (GPT Image 2, swappable)
│   │   │   └── duotone.py           # Pillow post-process + keyword cache
│   │   ├── sources/
│   │   │   ├── paste_link.py        # fetch + extract → brief w/ pinned source
│   │   │   └── awareness_calendar.py
│   │   ├── routes/
│   │   │   ├── brand.py             # GET/PUT brand kit
│   │   │   ├── picks.py             # GET daily picks (+ reroll)
│   │   │   ├── generate.py          # POST generate → slide content + hero URL
│   │   │   └── sources.py           # POST paste-link
│   │   └── db/
│   │       └── supabase.py          # client + queries
│   └── tests/
│
└── .github/
    └── workflows/                  # optional CI; Vercel/Railway auto-deploy on push
```

---

## 5. Environment variables

`backend/.env.example`:

```bash
# --- AI providers ---
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
LLM_MODEL_CHEAP=claude-haiku-4-5-20251001
LLM_MODEL_STRONG=claude-sonnet-5
IMAGE_MODEL=gpt-image-2

# --- Supabase ---
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_DB_URL=postgresql://...

# --- Cost / quality flags (Section 11) ---
IMAGE_QUALITY=medium          # medium | low  — test low after duotone
IMAGE_SIZE=1024x1536          # portrait
ENABLE_CRITIQUE=true          # draft→critique→refine on every post
ENABLE_PROMPT_CACHE=true

# --- CORS ---
FRONTEND_ORIGIN=https://your-app.vercel.app
```

`frontend/.env.local.example`:

```bash
NEXT_PUBLIC_API_URL=https://your-app.up.railway.app
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

Set the same keys in the Railway and Vercel dashboards for production. Never commit real values.

---

## 6. Pydantic contracts (the spine — create these first in Phase 2)

`backend/app/models/enums.py`:

```python
from enum import Enum

class Format(str, Enum):
    CAROUSEL = "carousel"
    SINGLE_IMAGE = "single_image"

class Approach(str, Enum):
    EDUCATIONAL = "educational"
    MYTH_VS_FACT = "myth_vs_fact"
    CHECKLIST = "checklist"
    STORY = "story"
    STAT_RESEARCH = "stat_research"
    QUESTION_REFLECTION = "question_reflection"
    FRAMEWORK = "framework"
    COMMON_MISTAKES = "common_mistakes"

class EntryPoint(str, Enum):
    A_MISTAKE = "a_mistake"
    A_QUESTION = "a_question"
    A_CONTRARIAN_TAKE = "a_contrarian_take"
    A_STAT = "a_stat"
    A_RELATABLE_MOMENT = "a_relatable_moment"

class Sensitivity(str, Enum):
    NORMAL = "normal"
    HEALTH = "health"
    SENSITIVE = "sensitive"
```

`backend/app/models/brand_kit.py`:

```python
from pydantic import BaseModel

class MoodPalette(BaseModel):
    primary: str                      # hex — duotone shadow
    secondary: str                    # hex — duotone highlight
    accent: str                       # hex — script word, masthead rule, CTAs

class VoiceRegister(BaseModel):
    poetic: list[str]                 # calm/poetic — quotes, feelings, story/reflection content
    direct: list[str]                 # grounded/direct — research/opinion content

class BrandKit(BaseModel):
    brand_name: str                   # full name, e.g. "Women's Growth Society"
    handle: str                       # e.g. "@womensgrowthsociety" — spelled out ONLY on
                                      # the closing template's footnote, for content that
                                      # circulates outside Instagram
    masthead_short: str               # e.g. "WGS" — appears on every slide's masthead
    niche: str
    audience: str

    voice_traits: list[str]
    voice_samples: VoiceRegister      # two registers — resolved per-post by approach, not one flat list
    forbidden: list[str] = []

    mood_palettes: dict[str, MoodPalette]   # keys: "wisdom" | "bold" | "celebratory"
    text_color: str                   # hex — shared across all moods
    background_color: str             # hex — shared across all moods
    font_heading: str                 # e.g. "Archivo Black"
    font_script: str                  # e.g. "Alex Brush" — one accent word only
    font_body: str                    # e.g. "Inter"

    default_tone: list[str]
    signature_cta: str | None = None
```

`taxonomy/voice_register.py` — the lookup that resolves which register a post uses, based on its approach (mirrors `APPROACHES`/`ENTRY_POINTS`):

```python
APPROACH_REGISTER = {
    "story": "poetic", "question_reflection": "poetic",
    "educational": "direct", "myth_vs_fact": "direct", "checklist": "direct",
    "stat_research": "direct", "framework": "direct", "common_mistakes": "direct",
}
```

**WGS's fully locked values** (seed these as the Phase 1 test fixture / first real row):

```python
WGS_BRAND_KIT = {
    "brand_name": "Women's Growth Society",
    "handle": "@womensgrowthsociety",
    "masthead_short": "WGS",
    "niche": (
        "Practical emotional intelligence and confidence-building for women "
        "unlearning people-pleasing and navigating career and self-worth."
    ),
    "audience": (
        "Women in their 20s-40s building a career while learning to trust "
        "themselves, and craving steady, honest encouragement over empty positivity."
    ),
    "voice_traits": ["supportive", "trusted", "encouraging", "calm", "grounded-in-facts"],
    "voice_samples": {
        "poetic": [
            "You don't have to shrink to keep the peace. Some rooms were never meant to hold all of you.",
            "The tears you're hiding today are just proof you're finally listening to yourself.",
            "Growth doesn't announce itself. It just quietly becomes the way you breathe.",
            "You're allowed to outgrow people who only ever loved the smaller version of you.",
            "Some days strength looks like getting up. Other days, it looks like finally resting.",
        ],
        # Revised 2026-07-15 (logbook #30) — see blueprint.md Section 4 for why.
        "direct": [
            "Rest isn't something you earn after you collapse. It's maintenance you schedule before your body forces the issue.",
            "Your cycle isn't an inconvenience you push through. It's data about your body you're free to actually use.",
            "Saying less to someone isn't cold. It's what happens once you stop over-explaining a decision that was already final.",
            "Research shows women are socialized to soften their opinions before they've even finished stating them. Naming the pattern doesn't undo it — but it's the first thing that has to happen.",
            "Confidence isn't a feeling you wait for. It's a skill you build one uncomfortable choice at a time.",
        ],
    },
    "forbidden": [
        "preachy", "bossy", "negative", "overly corporate", "fake positivity",
        "clickbait", "hustle-mindset language",
        "engagement-bait CTAs (e.g. 'comment ❤️ if...')",
    ],
    "mood_palettes": {
        "wisdom":      {"primary": "#4B3A6E", "secondary": "#F3EEF9", "accent": "#8A63D2"},
        "bold":        {"primary": "#8C3B2E", "secondary": "#F7E9DE", "accent": "#D9643F"},
        "celebratory": {"primary": "#6E4F17", "secondary": "#FCEDB8", "accent": "#E8A23D"},
    },
    "text_color": "#241C33",
    "background_color": "#FAF7FC",
    "font_heading": "Archivo Black",
    "font_script": "Alex Brush",
    "font_body": "Inter",
    "default_tone": ["warm", "encouraging"],
    "signature_cta": "Follow us for daily reminders that help you grow.",
}
```

`backend/app/models/topic.py`:

```python
from pydantic import BaseModel
from .enums import Format, Sensitivity

class Topic(BaseModel):
    id: str
    name: str
    categories: list[str]             # multi-tagged — browsable under many
    primary_category: str             # the ONE category counted on the masthead
    tone_defaults: list[str]
    suitable_formats: list[Format]
    seed_angles: list[str]            # 3–5 example sub-concepts
    knowledge_hints: list[str] = []
    requires_citation: bool = False
    sensitivity: Sensitivity = Sensitivity.NORMAL
```

`backend/app/models/brief.py`:

```python
from datetime import datetime
from pydantic import BaseModel
from .enums import Format, Approach, Sensitivity

class Source(BaseModel):
    title: str
    author: str | None = None
    url: str | None = None
    excerpt: str                      # only citable text
    retrieved_at: datetime

class ContentBrief(BaseModel):
    topic_id: str
    topic_name: str
    angle: str
    approach: Approach
    goal: str                         # educate | inspire | reflect | inform
    mood: str = "wisdom"              # wisdom | bold | celebratory — tagged w/ the angle

    format: Format
    slide_count: int                  # 1 for single image; 3–4 for carousel
    tone: list[str]
    brand_voice_samples: list[str]
    signature_cta: str | None = None

    requires_citation: bool = False
    sensitivity: Sensitivity = Sensitivity.NORMAL
    sources: list[Source] = []

    hero_image_prompt: str
    max_words_per_slide: int = 30
```

`backend/app/models/memory.py`:

```python
from datetime import date
from pydantic import BaseModel
from .enums import Format, Approach

class MemoryRecord(BaseModel):
    id: str
    date: date
    topic_id: str
    category: str                     # Topic.primary_category, denormalized for fast counting
    angle: str
    approach: Approach
    format: Format
    mood: str
    hook: str
    fingerprint: str                  # topic + angle + approach
    source_ids: list[str] = []
    status: str                       # draft | exported
```

**Masthead count query** (pure Python, no LLM, used by `brief_builder.py`):

```python
def next_masthead_number(category: str, memory: list[MemoryRecord]) -> str:
    n = 1 + sum(1 for r in memory if r.category == category and r.status == "exported")
    return f"{category.upper()} NO. {n:02d}"
```

---

## 7. Provider adapters (Phase 3)

`backend/app/providers/llm.py` — tiered, so callers ask for a tier, not a model:

```python
class LLMProvider:
    """Wraps Anthropic. Callers pass tier='cheap'|'strong'."""
    def complete(self, *, tier: str, system: str, prompt: str,
                 max_tokens: int, cache: bool = True) -> str: ...
```

`backend/app/providers/image.py` — swappable, so the vendor can change without touching the pipeline:

```python
class ImageProvider:
    """Wraps GPT Image 2 today; swap freely behind this interface."""
    def generate(self, *, prompt: str, size: str, quality: str) -> bytes: ...
```

`backend/app/providers/duotone.py`:

```python
def apply_duotone(image: bytes, shadow_hex: str, highlight_hex: str) -> bytes:
    """Pillow: desaturate, map shadows→shadow_hex, highlights→highlight_hex.
    Deterministic, free. Cache result by keyword."""
```

---

## 8. The render contract (Phase 1)

Implemented as `frontend/app/api/render/route.ts` using `@vercel/og` (bundles Satori + resvg):

```
POST /api/render
  body: {
    template_id: string,           # "carousel_cover" | "carousel_body" | "carousel_closing"
                                    # | "single_quote" | "single_stat"
    slides: [{ heading, body, ... }],
    masthead: { masthead_short, category, number },   # e.g. { "WGS", "MINDSET", "14" }
    tokens: {                      # the ALREADY-RESOLVED mood, not the raw BrandKit —
      primary, secondary, accent,  # backend picks mood_palettes[brief.mood] before calling
      text_color, background_color,
      font_heading, font_script, font_body
    },
    hero_image_url: string | null  # duotoned hero from backend — cover template only
  }
  → returns: PNG(s) at 1080×1350
```

The backend resolves `brief.mood` → `BrandKit.mood_palettes[mood]` before calling this route — the frontend never picks a mood, it only renders whatever palette it's handed. The JSX slide templates in `components/slides/` are the single source of truth: the editor renders them live for editing, and this route renders the same components to PNG for export. `Masthead.tsx` is shared across all five templates and is the one place that formats the `{masthead_short} — {category} NO. {n}` string.

---

## 9. Data model (Supabase / Postgres)

Minimal tables for Phase 1 (single user):

- `brand_kit` — one row (the creator's kit); `voice_samples` stored as two arrays (`poetic`, `direct`) that each grow independently as she edits/approves posts.
- `topics` — seeded from `topics.yaml` (or kept file-based and read at startup; DB optional for topics in Phase 1).
- `memory` — one row per generated post (`MemoryRecord`). Beyond the original fields, also carries `caption text`, `slides jsonb` (the same discriminated-union shape as `GeneratedPost.slides`, validated through it at write time), `exported_at timestamptz`, and `voice_trained_at timestamptz` (all added in #35, for the export-confirmation event; `exported_at`/`voice_trained_at` are nullable — meaningful-null, unset until content is genuinely persisted / voice training genuinely completes — two independent idempotency checks, not one shared guard).
- `image_cache` — keyword → Supabase Storage URL of the duotoned hero.
- `audit_log` — append-only record of every insert/update/delete on `brand_kit` and `memory`, through any path (app, dashboard, direct SQL), written by a `security definer` trigger (added in #34).
- Supabase Storage bucket `heroes/` — the duotoned images.
- Supabase Auth — one user.
- **RLS (tightened in #34):** `brand_kit`, `memory`, `image_cache`, and `audit_log` are service-role-only. The original `authenticated_full_access` policy (`FOR ALL` / `using(true)` / `with check(true)` — fully open to any authenticated session) is gone; `authenticated` is revoked entirely from all four tables, same as `anon` already was. Only the backend's service-role key (which bypasses RLS as a role property) can read or write.

---

## 10. Phase-by-phase build plan

### Phase 1 — Design foundation (prove the quality ceiling)

**Goal:** static, beautiful slide templates + the image/render path, before any AI. If a template looks generic with dummy text, no pipeline saves it.

**Build:** monorepo scaffold; `Masthead.tsx` + the 5 JSX slide templates, built to the **locked design spec below** (not placeholder styling — this is real, mockup-validated); `brand-tokens.ts` mapping resolved mood tokens to CSS vars; the duotone function; the `/api/render` route; a `/preview` page showing all five templates across all three moods.

**The locked design spec** (validated via HTML mockups before this build — see design system section of the blueprint):

- **Fonts:** Archivo Black (structural headline), Alex Brush (script accent — one word/phrase only, never more), Inter (body + masthead labels). All free Google Fonts — fetch the TTFs into `frontend/public/fonts/` for Satori to bundle.
- **Three moods**, same layout/fonts/text/background, only duotone pair + accent shift:
  - `wisdom`: primary `#4B3A6E`, secondary `#F3EEF9`, accent `#8A63D2`
  - `bold`: primary `#8C3B2E`, secondary `#F7E9DE`, accent `#D9643F`
  - `celebratory`: primary `#6E4F17`, secondary `#FCEDB8`, accent `#E8A23D`
  - shared: `text_color #241C33`, `background_color #FAF7FC`
- **Masthead** (`Masthead.tsx`, used at the top of all five templates): `{masthead_short}` — thin rule — `{category} NO. {n}`, small-caps, letter-spaced, ~65% opacity. Same masthead text on every slide within one carousel.
- **CarouselCover:** masthead top; below it a stacked headline — `font_heading` bold block word in the mood's accent color, then a `font_script` word/phrase directly beneath in `text_color`; a short kicker line in `font_body`; the hero photo anchored to the bottom of the slide via `margin-top: auto` (photo is a duotone-gradient placeholder for now — real image comes in Phase 3).
- **CarouselBody:** masthead top; no photo; a large statement in `font_body` bold, with one phrase set in `font_script` at the mood's accent color for emphasis.
- **CarouselClosing:** background = mood's `primary` color, text = mood's `secondary`. Masthead pinned top in normal flow. Everything else lives in a wrapper with `flex: 1; display: flex; flex-direction: column; justify-content: center` — **not** `justify-content` on the whole slide, which incorrectly pulls the masthead down with it. Inside that wrapper, in order: the takeaway line (bold, body font), the `font_script` signature ("with you,"), the `signature_cta` sentence set at real body-copy reading weight (not the small letter-spaced label style — a full sentence in that style reads as fine print), then a tiny letter-spaced footnote line spelling out `handle` (e.g. "@womensgrowthsociety") — the only place the full handle appears; every other template shows just `masthead_short`.
- **SingleQuote:** masthead top; an oversized `font_script` quotation mark behind the text at ~28% opacity, positioned top-left; the quote itself in `font_body` semibold, offset below the mark. No photo.
- **SingleStat:** masthead top; small uppercase kicker in `font_body`; a large number in `font_heading` at the mood's accent color; one supporting line in `font_body` below. No photo.
- **Canvas:** all templates 1080×1350, content kept inside a centered 3:4 safe zone.

**Done when:** you can switch mood on any template and watch it re-skin correctly (masthead/fonts/layout unchanged, only duotone+accent shift); the closing slide's masthead stays pinned top with its body block genuinely centered below it (not pushed to the bottom, not touching the masthead); you can render a full carousel (cover + body + closing) to PNGs from placeholder JSON; the cover shows a duotone-gradient placeholder in the mood's colors; every template looks sharp and on-brand with dummy WGS content, not generic.

> **Claude Code prompt — Phase 1**
> "Scaffold a monorepo per `docs/implementation-guide.md` Section 4 (only the `frontend/` parts needed now, plus `backend/app/providers/duotone.py`). Frontend: Next.js App Router + pnpm + TypeScript, fonts Archivo Black / Alex Brush / Inter self-hosted from Google Fonts in `public/fonts/`. Build `components/slides/Masthead.tsx` and the 5 JSX slide templates (CarouselCover, CarouselBody, CarouselClosing, SingleQuote, SingleStat) exactly to the locked design spec in `implementation-guide.md` Section 10 Phase 1 — including the three named mood palettes, the shared text/background colors, and the closing slide's masthead-pinned-top / body-centered-in-flex:1 layout pattern (do not use justify-content on the whole slide for that one). All templates sized to 1080×1350 with a centered 3:4 safe zone, reading every color/font from a resolved `tokens` object (never hardcoded) via `lib/brand-tokens.ts`. Implement `app/api/render/route.ts` using `@vercel/og` per the contract in Section 8 (`template_id`, `slides`, `masthead`, `tokens`, `hero_image_url`). Build a `/preview` page using the WGS_BRAND_KIT fixture from Section 6 that renders all 5 templates × all 3 moods (a 5×3 grid) with placeholder copy, so mood-switching can be visually verified across the whole set. In the backend, implement only `apply_duotone` in Pillow with a keyword cache stub, returning a mood-colored gradient placeholder for now. Don't add any LLM or image-gen calls yet. When finished, invoke phase-verifier against this phase's Done-when criteria (Section 10), report results, then stop and wait for my confirmation."

---

### Phase 2 — Data spine

**Goal:** the contracts and the authored taxonomy exist and validate.

**Build:** all Pydantic files in `models/`; `approaches.py` + `entry_points.py`; `topics.yaml` with 40–60 topics (start with 15–20 to unblock, expand later); a loader that validates `topics.yaml` against the `Topic` model on startup; `brief_builder.py` producing a valid `ContentBrief` from a topic + chosen angle/approach/format + brand kit.

**Done when:** `topics.yaml` loads and validates; `brief_builder` returns a well-formed `ContentBrief`; the two global lists are enums the rest of the code imports.

> **Claude Code prompt — Phase 2**
> "Create the Pydantic v2 contracts exactly as in `implementation-guide.md` Section 6 (`enums.py`, `brand_kit.py`, `topic.py`, `brief.py`, `memory.py`). Create `taxonomy/approaches.py`, `taxonomy/entry_points.py`, and `taxonomy/voice_register.py` (the `APPROACH_REGISTER` dict from Section 6) from the enums. Create `taxonomy/topics.yaml` with 18 starter topics across the categories in the blueprint (mindset, career, wellness, women's health, relationships, society, inspiring women), each with a `primary_category` (must be exactly one of its `categories` entries — this is what the masthead counts against), 3–5 `seed_angles`, `suitable_formats`, `tone_defaults`, and correct `sensitivity`/`requires_citation` (health topics = HEALTH + citation required). Add a loader that validates the YAML against `Topic` at startup, including a check that `primary_category` is present in `categories`, and fails loudly on error. Implement `engine/brief_builder.py`: given a topic_id, angle, approach, mood, format, and a BrandKit, resolve the voice register via `APPROACH_REGISTER[approach]` and inject only that list (`BrandKit.voice_samples.poetic` or `.direct`) as `brand_voice_samples`, and return a valid ContentBrief with the masthead number computed via `next_masthead_number()` (Section 6) against current content memory. When finished, invoke phase-verifier against this phase's Done-when criteria (Section 10), report results, then stop and wait for my confirmation."

---

### Phase 3 — Generation

**Goal:** a brief in, a validated post out.

**Build:** `providers/llm.py` (tiered, prompt-caching aware) and `providers/image.py` (GPT Image 2); `angle_engine.py` (sample a cell from `Topic.seed_angles` × approaches × entry points, filtered against recent memory); `generator.py` (draft→critique→refine on the strong tier, gated by `ENABLE_CRITIQUE`); `validator.py` (brand voice + forbidden terms, citation check when required, word limits, repetition via fingerprint); `memory.py` (write records, append exports/edits to the correct `voice_samples` register — `poetic` or `direct`, per the post's resolved register).

**Done when:** calling `generate(topic_id, format)` returns slide content + caption + hashtags + a duotoned hero URL, passes validation, and writes a `MemoryRecord`; re-running the same topic yields a *different* angle.

> **Claude Code prompt — Phase 3**
> "Implement the generation pipeline. `providers/llm.py`: an Anthropic wrapper with `tier` ('cheap'→LLM_MODEL_CHEAP, 'strong'→LLM_MODEL_STRONG), prompt caching on the system prompt + brand voice block when ENABLE_PROMPT_CACHE. `providers/image.py`: GPT Image 2 via the OpenAI images API at IMAGE_SIZE/IMAGE_QUALITY, returning bytes; then duotone + cache. `engine/angle_engine.py`: sample one (sub-concept × approach × entry-point) cell, grounded by Topic.seed_angles and BrandKit, excluding fingerprints already in recent memory for that topic; use the cheap tier to write the specific angle sentence AND tag a `mood` ("wisdom"|"bold"|"celebratory") in the same call/response — bundle both into one JSON output so mood tagging adds no extra API call — with a deterministic fallback to "wisdom" if the field is missing or invalid. `engine/generator.py`: strong-tier draft → self-critique against brand+brief → refine, producing per-slide copy + caption + hashtags; skip critique if ENABLE_CRITIQUE is false. `engine/validator.py`: brand-voice/forbidden check, citation check (claims ⊆ sources) when requires_citation, per-slide word limit, repetition check. `engine/memory.py`: persist MemoryRecord and append approved copy to the correct register in BrandKit.voice_samples (poetic or direct, matching the post's approach via APPROACH_REGISTER). Wire `routes/generate.py` to run image and text lanes in parallel and return slide content + hero URL. When finished, invoke phase-verifier against this phase's Done-when criteria (Section 10), report results, then stop and wait for my confirmation."

---

### Phase 4 — Surfaces

**Goal:** she has something to open to, and can turn any article into a post.

**Build:** `selector.py` (coverage-aware, date-seeded 3 picks, ~2 evergreen + 1 timely, enforce category variety, limited reroll; precompute only hook + thumbnail concept nightly); `routes/picks.py`; `sources/paste_link.py` (readability/trafilatura extraction → brief with pinned `Source`); `sources/awareness_calendar.py` (a small dated list, surfaced near dates).

**Done when:** `GET /picks` returns 3 stable-for-the-day picks with hooks; a pasted URL yields an attributed brief; an awareness day near today appears as a pick.

> **Claude Code prompt — Phase 4**
> "Implement `engine/selector.py`: pick 3 daily topics seeded by today's date (stable within the day), weighted by brand niche and by coverage (boost topics/approaches unused recently per memory), enforce category variety, mix ~2 evergreen + 1 timely, and expose a limited `reroll`. Precompute only a hook + thumbnail concept per pick (cheap tier) as a callable batch job; full generation happens on tap via Phase 3. `sources/paste_link.py`: fetch a URL, extract main text with trafilatura, build a ContentBrief with the article pinned as a Source and requires_citation=True. `sources/awareness_calendar.py`: a dated list of women-focused awareness days; surface any within N days as a timely pick. Add `routes/picks.py` and `routes/sources.py`. When finished, invoke phase-verifier against this phase's Done-when criteria (Section 10), report results, then stop and wait for my confirmation."

---

### Phase 5 — Mobile flow

**Goal:** the whole loop works on a phone.

**Build:** Home (today's pick + 3 picks + browse + paste); topic+format selection with the AI-proposed approach (one-tap accept / swipe alternatives); generate → editor (swipe slides, inline text edit, regenerate-this-slide, reshuffle-image → reruns only the image lane); export (render PNGs via `/api/render`, save to camera roll, copy caption/hashtags). Prototype the editor early and roughly before polishing.

**Done when:** from the home screen she can produce, edit, and export a carousel on a phone, and the exported PNGs match the editor preview.

> **Claude Code prompt — Phase 5**
> "Build the mobile-first screens wired to the backend via `lib/api.ts`. Home (`app/page.tsx`): today's pick + 3 daily picks + browse + paste-link entry. `app/generate/page.tsx`: topic + format, showing the AI-proposed approach with a one-line reason and a one-tap accept plus swipe-to-alternatives. `app/editor/page.tsx`: render slides from the same `components/slides` templates, swipe between them, tap-to-edit text inline, 'regenerate this slide' and 'reshuffle image' (image-lane only). `app/export/page.tsx`: call `/api/render` for final PNGs, offer save-to-photos and copy-caption. Keep the editor interaction simple and touch-first; no desktop canvas. When finished, invoke phase-verifier against this phase's Done-when criteria (Section 10), report results, then stop and wait for my confirmation."

---

### Phase 6 — Deployment

**Goal:** one URL, works on her phone.

**Build:** push to GitHub; connect `frontend/` to Vercel and `backend/` to Railway (two deploy configs / root directories); set env vars in both dashboards; restrict backend CORS to the Vercel domain; create the Supabase project, tables, Storage bucket, and one auth user.

**Done when:** the Vercel URL loads on her phone, calls Railway successfully, and a full generate→export works end to end in production.

> **Claude Code prompt — Phase 6**
> "Prepare for deployment: add `CORSMiddleware` to `main.py` restricted to FRONTEND_ORIGIN; add a `pyproject.toml`/`uv` build and a Railway start command (`uvicorn app.main:app`); document root-directory settings for Vercel (`frontend/`) and Railway (`backend/`); write the Supabase schema SQL for `brand_kit`, `memory`, `image_cache` and the `heroes` Storage bucket; add `lib/supabaseClient.ts` and backend `db/supabase.py`. Produce a short `DEPLOY.md` with the exact click-path for connecting the repo to Vercel and Railway and setting env vars. When finished, invoke phase-verifier against this phase's Done-when criteria (Section 10), report results, then stop for my confirmation that the live app works end to end."

---

## 11. Cost guardrails

Bake these in from Phase 3 so spend stays predictable:

- **`IMAGE_QUALITY` flag** — the biggest lever. Start `medium`; run the duotone A/B early and, if indistinguishable, set `low` (≈8× cheaper images, pulling the whole app to ~$10/mo).
- **`ENABLE_CRITIQUE`** — on by default (it's your quality moat and volume is tiny); a kill-switch if you ever need it.
- **`ENABLE_PROMPT_CACHE`** — cache the system prompt + brand voice block across the three strong-tier calls per post (~90% off cached input).
- **Model tiering** — angles and pitches on Haiku; only copy + critique on Sonnet. Never route pitches to the strong tier.
- **Generate-on-tap** — daily picks precompute pitches only; full posts generate when tapped, so unopened picks cost almost nothing.
- **Usage log** — log tokens + image count per generation to a `usage` table so you can see real monthly spend and which lever to pull.

---

## 12. Definition of done — Phase 1 overall

She can: complete onboarding (brand kit) → open the app to 3 curated picks → tap one → accept the proposed approach → generate a 3–4 slide carousel in her voice with a duotoned cover, correct mood palette, and a masthead reading `WGS — {CATEGORY} NO. {n}` on every slide → swipe-edit and reshuffle on her phone → export PNGs + caption → and tomorrow's picks avoid what she just made, with the masthead count incrementing correctly for that category on her next post. All on one URL, both providers pay-as-you-go, running under ~$20/month.
