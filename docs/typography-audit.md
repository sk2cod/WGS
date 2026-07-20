# Typography audit

Exact font-family, size, weight, letter-spacing, and line-height for every text
element across all slide templates, pulled directly from component source —
not inferred from rendered output. Re-run whenever template styles change;
re-verify against the files before trusting this if it's been a while.

**Last verified:** 2026-07-20, against working-tree state of
`frontend/components/slides/*.tsx` and `frontend/lib/wgs-brand-kit.ts`
(re-run confirmed no typography values changed from the prior pass despite
other uncommitted changes to `CarouselClosing.tsx`, `ConversationSlide.tsx`,
and `types.ts` that day — those touched props/copy, not styles).

No dedicated typography-token file exists (no `tokens.ts`/`typography.ts`).
Every size/weight/spacing/line-height value below is a per-component inline
literal in the `.tsx` files. Only the three font-family strings are
centralized, in `WGS_BRAND_KIT` (`frontend/lib/wgs-brand-kit.ts:51-53`):

- `font_heading` = Archivo Black
- `font_script` = Alex Brush
- `font_body` = Inter

All templates share the same 1080×1350 canvas, 72px top/bottom padding, and
safe-zone-inset side padding from `SlideFrame.tsx` — no template overrides
frame-level spacing.

"not set" below means the JSX literally omits that CSS property (Satori/browser
falls back to its own default — normal weight, normal line-height) — there is
no inherited design-system default standing in for it.

## Shared: Masthead (`Masthead.tsx`)

Rendered atop every template. Color defaults to `tokens.text_color`, overridden
to `tokens.secondary` only in `CarouselClosing` (dark background).

| Element | Font family | Size | Weight | Letter-spacing | Line-height |
|---|---|---|---|---|---|
| `masthead_short` text | Inter (font_body) | 22 | 600 | 3 | not set |

## CarouselCover (`CarouselCover.tsx`)

| Element | Font family | Size | Weight | Letter-spacing | Line-height |
|---|---|---|---|---|---|
| `headline_word` | Archivo Black (font_heading) | 96 | not set | not set | 1 |
| `script_word` | Alex Brush (font_script) | 72 | not set | not set | 1.15 |
| `kicker` | Inter (font_body) | 30 | 400 | not set | not set |

## CarouselBody (`CarouselBody.tsx`)

| Element | Font family | Size | Weight | Letter-spacing | Line-height |
|---|---|---|---|---|---|
| `statement_pre` words | Inter (font_body) | 56 | 700 | not set | 1.25 |
| `statement_script` | Alex Brush (font_script) | 64 | 400 | not set | 1.25 |
| `statement_post` words | Inter (font_body) | 56 | 700 | not set | 1.25 |

## CarouselBodyTeaching (`CarouselBodyTeaching.tsx`)

| Element | Font family | Size | Weight | Letter-spacing | Line-height |
|---|---|---|---|---|---|
| `heading` | Archivo Black (font_heading) | 40 | not set | not set | 1.2 |
| `body` | Inter (font_body) | 36 | 500 | not set | 1.5 |

## CarouselClosing / "ClosingSlide" (`CarouselClosing.tsx`)

Background = mood's `primary`; text = mood's `secondary`. Per logbook #39
round 8, only `takeaway` renders here now — `signature`/`cta`/`handle` were
removed from display or relocated to `ConversationSlide`.

| Element | Font family | Size | Weight | Letter-spacing | Line-height |
|---|---|---|---|---|---|
| `takeaway` | Inter (font_body) | 48 | 700 | not set | 1.3 |

## SingleQuote / "QuoteSlide" (`SingleQuote.tsx`)

| Element | Font family | Size | Weight | Letter-spacing | Line-height |
|---|---|---|---|---|---|
| Decorative `"` mark | Alex Brush (font_script) | 420 | not set | not set | 1 (opacity 0.28) |
| `quote` text | Inter (font_body) | 52 | 600 | not set | 1.35 |

## SingleStat / "StatSlide" (`SingleStat.tsx`)

| Element | Font family | Size | Weight | Letter-spacing | Line-height |
|---|---|---|---|---|---|
| `kicker` | Inter (font_body) | 24 | 600 | 3 | not set (opacity 0.65) |
| `number` | Archivo Black (font_heading) | 200 | not set | not set | 1 |
| `supporting_line` | Inter (font_body) | 32 | 400 | not set | 1.4 |

## ConversationSlide (`ConversationSlide.tsx`)

The real CTA/question slide (logbook #39, round 7 — structural addition;
round 8 — `cta`/`handle` relocated here from `CarouselClosing`).

| Element | Font family | Size | Weight | Letter-spacing | Line-height |
|---|---|---|---|---|---|
| `label` | Inter (font_body) | 22 | 600 | 1 | not set |
| `question` | Inter (font_body) | 52 | 700 | not set | 1.3 |
| `invite` | Alex Brush (font_script) | 40 | not set | not set | not set |
| `cta` | Inter (font_body) | 24 | 400 | not set | 1.4 |
| `handle` | Inter (font_body) | 16 | 600 | 3 | not set (opacity 0.65) |

## Cross-cutting observations

- `textTransform: "uppercase"` appears on: Masthead, CarouselCover's
  `headline_word`, CarouselBodyTeaching's `heading`, SingleStat's `kicker`,
  and ConversationSlide's `handle` — always paired with letter-spacing.
- Every `font_heading` / `font_script` usage across templates omits an
  explicit `fontWeight` — both fonts are effectively single-weight in this
  project's locked font set, so weight is left to the font file itself.
- `opacity` is used as a de-emphasis technique on kickers/footnotes (Masthead
  0.65, SingleStat kicker 0.65, ConversationSlide handle 0.65, SingleQuote
  decorative mark 0.28) rather than a lighter text color.
