# Logbook — full build history, issues, and design deviations

Change log covering every phase of the build: what was implemented, every issue
reported along the way, how each was fixed, and where the result deviates from
`blueprint.md` / `implementation-guide.md`. Treat `CLAUDE.md`'s "Working notes" /
"Environment" sections as the current operating rules; this file is the history of
how we got there.

Reconstructed from git history (`git log`) plus the live deployment session —
commit messages for the earlier phases were already detailed, so entries 1–4 are a
faithful translation of those, not a reinterpretation.

---

## 1. Phases 1–2 — design foundation and data spine

Built exactly to `implementation-guide.md` Section 10: the five locked slide
templates (`Masthead`, `CarouselCover`, `CarouselBody`, `CarouselClosing`,
`SingleQuote`, `SingleStat`), the three duotone moods, `/api/render` via
`@vercel/og`, the `/preview` grid, and the Pydantic contracts + authored taxonomy
(`topics.yaml`, `approaches.py`, `entry_points.py`, `voice_register.py`).

**No deviations** — this phase is straightforward scaffolding matching the spec.

---

## 2. Phases 3–5 — generation, surfaces, mobile flow (initial build)

Built per Section 10: the tiered LLM/image providers, `angle_engine.py` (sample
sub-concept × approach × entry-point), `generator.py` (draft → critique → refine),
`validator.py`, `memory.py` (file-backed at this point — Supabase wiring was
explicitly deferred, see #9), the daily-picks selector, paste-link/awareness-calendar
sources, and the mobile screens (home → generate → editor → export).

**No deviations at this point** — the two refinements below happened afterward, as
real generated output revealed problems the spec couldn't have anticipated without
seeing it.

---

## 3. Design refinement: carousel body content was landing in the caption, not the slides

**Problem found:** the original `carousel_body` slide shape (`statement_pre` /
`statement_script` /`statement_post` — a single sentence with one emphasized phrase)
never had room for real substance. For approaches that need to actually teach
something (`story`, `educational`, `framework`, `myth_vs_fact`, `common_mistakes`),
the generator was compensating by dumping the real content into the caption as a
paragraph — leaving the slides themselves thin and the caption doing work it was
never meant to do.

**Fix — a sixth slide template, `carousel_body_teaching`:** approaches needing real
teaching room now get **two** `carousel_body_teaching` slides (1–2 full sentences of
actual substance each — heading + body) instead of one `carousel_body` fragment.
Which shape a post gets is decided once, at brief-build time
(`TEACHING_BODY_APPROACHES` in `taxonomy/approaches.py`), so slide count stays
consistent through validation. Added end-to-end on the frontend too: types,
`/api/render` case, `SlideRenderer`, the `/preview` grid.

**Also layered into the generation prompts in the same pass** (`generator.py`):
- A real structural definition per approach (`_APPROACH_DEFINITIONS`) — previously a post could be labeled `framework` without its content actually delivering a framework's shape.
- Kicker discipline: must disambiguate the topic through a natural sentence, never degrade into a taxonomy label (e.g. never "Career — Salary Negotiation").
- Peer-to-peer active voice, everyday concrete specificity, practical actionability, and judgment-based "saveability" (a reusable takeaway, only when the topic genuinely has one to give).
- **Caption discipline**: the caption's job is a hook, optionally one added closing thought — never a restatement of slide content. `critique_post` now checks all of the above, not just voice/tone/length.

**Deviation:** `implementation-guide.md`'s locked Phase 1 design spec names exactly
five slide templates (`CarouselCover`, `CarouselBody`, `CarouselClosing`,
`SingleQuote`, `SingleStat`). `CarouselBodyTeaching` is a sixth, added after the
fact because the original `CarouselBody` shape structurally couldn't hold what
several approaches needed to say. `CarouselBody` itself still exists and is still
used for the approaches that only need a single emphasized statement —
`checklist`, `stat_research`, and `question_reflection`.

---

## 4. Design refinement: hero images were generic and topic-disconnected

**Problem found:** `hero_image_prompt` was built from the full multi-sentence
angle text. Image models can't visually translate an argument, so this produced
generic abstract clichés (stairs, winding paths) with no real connection to the
specific topic.

**Fix — `visual_subject`:** the same cheap-tier LLM call that already produces
`angle`/`mood`/`reason` in `angle_engine.py` now also produces `visual_subject` in
the same response (bundled — no added API cost for the main angle-engine path):
5–15 words naming one concrete, photographable image/object/scene genuinely tied to
the specific topic and angle — never an abstract mood word ("transformation",
"growth") and never a stock-photo trope (a staircase, a winding path).
`hero_image_prompt` is now built from `visual_subject` via a shared
`_hero_image_prompt()` helper, threaded through `propose → accept → generate` so the
real production flow benefits, not just direct calls. Also fixed a string-quoting
bug this surfaced (raw text nested inside manually-added quotes broke on
apostrophes already present in the source text).

Paste-link briefs (`sources/paste_link.py`) don't go through the angle engine at
all, so they got the same fix via a **separate, real added cost**: a new cheap-tier
call that grounds `visual_subject` in the article's title and excerpt instead of
the bare headline.

**Not a locked-spec deviation** — `hero_image_prompt` was always going to need some
grounding strategy; the blueprint didn't specify one, so this is filling a gap
rather than contradicting a decision.

---

## 5. Phase 6 — initial deployment

**What was built, exactly per `implementation-guide.md` Section 10:**
- Backend deployed to Railway (project `wgs-backend`), `uvicorn app.main:app` via `railway.json`.
- Frontend deployed to Vercel (project `wgs`).
- `CORSMiddleware` restricted to `FRONTEND_ORIGIN`, updated to the real Vercel URL and redeployed once the frontend existed (the guide's specified sequencing).
- Supabase schema created: `brand_kit`, `memory`, `image_cache` tables + `heroes` Storage bucket (`backend/app/db/schema.sql`), plus `backend/app/db/supabase.py` (client + queries) and `frontend/lib/supabaseClient.ts`.
- `DEPLOY.md` written documenting the click-path.

**Deviation — domain naming:** the guide didn't anticipate the requested project name (`wgs`) being available as a Vercel project but not as a bare `wgs.vercel.app` subdomain (`.vercel.app` names are global across all Vercel users, independent of per-account project names). Vercel auto-assigned `wgs-two.vercel.app` as the project's default domain; `wgs-studio.vercel.app` was separately registered as a proper project domain to serve as the clean canonical URL. Both domains exist and both matter — see #10.

**Deviation — Vercel deployment protection:** new Vercel projects default to SSO/authentication protection on non-custom domains, which would have blocked the creator from ever loading the app on her phone. Disabled via `vercel project protection disable wgs --sso` — not mentioned in the guide since it predates this Vercel account default.

---

## 6. Railway env vars only partially applied

**Symptom:** after the first backend deploy, only `FRONTEND_ORIGIN` was actually set on Railway — `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `SUPABASE_*`, and 8 other keys were silently missing, even though the push command reported success for all of them.

**Root cause:** the bulk `railway variable set` loop didn't pass `--service wgs-backend`. Without an explicit service target, the sets appeared to succeed but didn't persist against the real service.

**Fix:** re-ran the push with `--service wgs-backend` on every call, verified all 12 keys were present via `railway variables --kv` before redeploying.

**Not a blueprint deviation** — implementation detail of the CLI, not the architecture.

---

## 7. `/generate` intermittently 500ing with `JSONDecodeError`

**Symptom:** `POST /generate` (the strong-tier, Sonnet-driven path) failed roughly 1 in 3 calls with `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)` in `_parse_post`. The cheap-tier `/generate/propose` (Haiku) never failed.

**Root cause:** `claude-sonnet-5` defaults **extended thinking** on when the `thinking` param is omitted, with an uncontrolled internal token budget. That budget can consume the entire `max_tokens` allotment, leaving zero tokens for the actual JSON response — confirmed directly: one repro run showed `stop_reason: max_tokens`, `content block types: ['thinking']` only, no `text` block at all.

**Fix:** `backend/app/providers/llm.py` now passes `thinking={"type": "disabled"}` on every Anthropic call (both tiers, one shared `complete()` method). Verified via repeated live-API calls: 5/5 direct `draft_post` calls succeeded cleanly post-fix, versus failing before it.

**Not a blueprint deviation** — a real-model-behavior bug, not a design choice. `implementation-guide.md` predates `claude-sonnet-5`'s extended-thinking default.

---

## 8. Login screen + Row Level Security (explicit follow-up request, beyond Phase 6's written scope)

`implementation-guide.md` Section 10's Phase 6 "Build" list only calls for the Supabase schema, storage bucket, and one auth user to exist — it does not call for a login UI or RLS policies. Both were added afterward on direct request:

- `frontend/app/login/page.tsx` + `frontend/components/AuthGate.tsx`: gates every route behind a Supabase Auth session (client-side check + redirect), wired to the one real auth user created directly in the Supabase dashboard.
- RLS enabled on `brand_kit`, `memory`, `image_cache` (`backend/app/db/schema.sql`): full access for the `authenticated` role, none for `anon`. The backend's `service_role` key bypasses RLS entirely, so this only closes off the public `anon` key that ships inside the frontend JS bundle.
- Verified with a throwaway test user (created, exercised, then deleted): anon reads return empty/`401`, authenticated reads/writes succeed.

**Deviation:** this is new functionality, not in the original design docs. Recorded here rather than silently folded into "Phase 6 as originally scoped."

---

## 9. Memory + Brand Kit migrated from local disk to Supabase (explicit follow-up request)

Also beyond Phase 6's literal build list — `engine/memory.py`'s own docstring before this change said outright: *"File-backed for now — no Supabase wiring until Phase 6 — but kept behind a small store class so swapping the backing store later doesn't touch callers."* Phase 6 as literally written only asked for the schema and a typed client to exist, not for the engine to actually use them. This was completed as a follow-up migration:

- `MemoryStore()` (no `path` arg — how every route constructs it) now reads/writes the real Supabase `memory` table.
- `MemoryStore(path=...)` (how every test constructs it) is unchanged — still file-backed, still fully hermetic, zero test changes needed beyond this.
- `taxonomy/wgs_brand_kit.get_brand_kit()` added: reads the `brand_kit` row from Supabase, self-seeding it from the existing `WGS_BRAND_KIT` constant on first call (no separate seed script). Routes swapped the constant for this accessor.
- **Verified against an actual restart, not just a same-process read/write:** seeded one `status="exported"` record directly in Supabase, confirmed the masthead counter reflected it (`MINDSET NO. 02`) via a live `/generate` call, ran a real `railway up` (full container rebuild — Railway's local filesystem is wiped on every redeploy, which is exactly what the old file-backed store couldn't survive), then confirmed the masthead counter was *still* `MINDSET NO. 02` post-restart and the exact seeded row (by ID) was still present.

**Not a blueprint deviation in the architectural sense** — this is precisely what Section 9 of the guide describes as the target state. It's logged here because it happened as an explicit later request, not inside the original Phase 6 pass.

---

## 10. Vercel domain confusion: removing `wgs-two.vercel.app` broke the dashboard

**What happened:** asked whether `wgs-two.vercel.app` (Vercel's auto-assigned default domain, see #5) served any purpose beyond `wgs-studio.vercel.app` (the deliberately registered canonical domain). Nothing in code, CORS config, or docs referenced it, so it was removed via `vercel alias remove`.

**Symptom:** the Vercel dashboard's project Overview then showed no production domain at all, and the Deployments tab stopped highlighting any deployment as "Production" — even though the app itself kept serving fine the whole time through `wgs-studio.vercel.app` (dashboard bookkeeping and actual request routing are two separate systems in Vercel, and they diverged).

**Root cause:** `wgs-two.vercel.app` isn't a discardable duplicate — Vercel bakes one auto-assigned `.vercel.app` domain into a project's metadata as *the* canonical default. `vercel project ls` kept reporting it as the "Latest Production URL" even after deletion (a dead reference, not a live fallback to another domain). Deleting it broke the dashboard's domain/production bookkeeping without breaking actual traffic routing.

**Fix:** restored the alias (`vercel alias set <deployment> wgs-two.vercel.app`); dashboard returned to normal immediately.

**Lesson, not a deviation:** don't remove Vercel's auto-assigned default `.vercel.app` domain even when nothing in the codebase references it directly.

---

## 11. Phone report: "Load failed" on Generate

**Symptom:** tapping Generate on a real topic (carousel format) on a phone produced a generic "Load failed" — the message a mobile browser's `fetch()` throws on a genuine network-level failure (timeout/dropped connection), not a clean HTTP error response.

**Investigation:** measured the full `/generate` pipeline directly against production, isolating each stage:
- Text lane (draft → critique → refine, three serial Sonnet calls): a stable ~29.5s.
- Image lane (GPT Image 2 at `IMAGE_QUALITY=medium`): **39–112 seconds, highly variable**, including one call that didn't finish inside a 2-minute window.

Since the two lanes run in parallel (`asyncio.gather`), total request time is `max(text, image)` — so the image lane, not the text lane, was the dominant and most variable cost, easily explaining a mobile timeout.

**Fix:** switched `IMAGE_QUALITY` from `medium` to `low` after visually confirming the duotoned output is indistinguishable (this was already flagged in `CLAUDE.md` as a planned-but-not-yet-run experiment). Re-measured live: **consistently 20–32 seconds**, no more 100+ second outliers. Also ~8x cheaper per the guide's own cost section.

**Not a blueprint deviation** — this is the experiment `implementation-guide.md`'s cost guardrails section explicitly anticipated ("Start medium; run the duotone A/B early and, if indistinguishable, set low").

---

## 12. "render failed for carousel_cover: 500" on Export

**Symptom:** after fixing #11, generation succeeded but tapping Export failed with `render failed for carousel_cover: 500` from `lib/render-client.ts`.

**Investigation, ruling things out in order:**
1. Hypothesized the ~2.86MB base64-embedded hero image was too large for `@vercel/og` / the Vercel function payload → **ruled out**: a tiny 1×1 placeholder image failed identically.
2. Pulled full Vercel function logs directly (`vercel logs --json`) and found the real error: `Cannot find module '.../next/dist/compiled/@vercel/og/index.node.js'` — a file that Next.js's own internal `og/image-response` module requires dynamically at runtime, and that genuinely exists in `node_modules` locally.
3. Confirmed via `vercel inspect` that the deployed build really was the latest commit — this wasn't a stale-deployment issue.

**Root cause:** Next.js 16's **default Turbopack production build was silently skipping the file-tracing step** needed to bundle that compiled module into the deployed Vercel serverless function. Confirmed by the build output itself: the webpack build explicitly runs a "Collecting build traces ..." step; the Turbopack build never printed it at all.

**Attempted fixes that did NOT work** (kept here so they aren't tried again blind):
- `serverExternalPackages: ["@vercel/og"]` — no effect; the import is routed through Next's own internal proxy for this package, not a normal external-package resolution path.
- `outputFileTracingIncludes` pointed at the symlinked `node_modules/next/...` path — caused a *different*, harder deploy-time failure: `"The framework produced an invalid deployment package... files in symlinked directories"` (pnpm's node_modules layout is symlink-based).
- `outputFileTracingIncludes` pointed at the real, non-symlinked `.pnpm/...` store path — deployed without error this time, but the runtime 500 persisted (and this path is fragile anyway: it's hash-suffixed and changes on dependency updates).

**Actual fix:** `frontend/package.json`'s `build` script changed to `next build --webpack`, forcing the webpack build pipeline instead of Turbopack. Confirmed via direct testing against the live deployment: all slide templates render `200`, including with the real ~2.86MB hero image, and the rendered PNG output was visually verified correct.

**Also added while fixing this:** the render route's `@vercel/og` import is now a dynamic `await import(...)` inside a `try/catch` (was a static top-level import, which meant the original crash happened at module-load time, before any of the route's own error handling could run). Any future render failure now returns a real JSON `{error: ...}` body instead of Next's opaque generic 500 page — purely defensive, doesn't change behavior when rendering succeeds.

**Deviation:** `CLAUDE.md`'s locked decision — *"Rendering: Satori via `@vercel/og`, on the frontend (Next.js route) — no headless browser, ever"* — is unchanged and still true. The deviation is narrower: **the frontend must build with webpack, not Next 16's default Turbopack**, or `/api/render` breaks in production while still working fine locally (`next dev` and local `next start` never surfaced this — it's Vercel-deployment-specific). Documented as a standing rule in `CLAUDE.md`'s Environment section so it isn't silently reverted later.

---

## 13. Confirmed: generate → render → export works end to end on device

**Report:** after #11 and #12 landed, the creator confirmed directly on her phone that a real generate → render → export pass completes correctly — not just synthetic verification from this side (curl calls, local repro scripts).

**Status:** this closes out the "Load failed" (#11) and "render failed: 500" (#12) issues as genuinely resolved in real usage, not just in isolated testing against production. No further action needed on either.

**Still open, not yet stress-tested (carried over from prior sessions, not re-raised as active bugs):**
- `critique_post`/`refine_post` share the same JSON-parsing shape as `draft_post` (#7's fix covers all three via the shared `LLMProvider.complete()` method), but only `draft_post` was directly repro-tested against the live API before/after the `thinking` fix. Worth a dedicated stress test if a similar `JSONDecodeError` ever resurfaces.
- The hero-image cache (`providers/duotone.py`, keyed by `topic_id` + mood palette) is rarely hit in practice because `angle_engine.py` resamples `mood` randomly on every call, changing the cache key almost every time. Not a bug, just a missed efficiency/cost opportunity.

---

## 14. Citation-required taxonomy topics silently rewriting content away from the accepted angle

**Symptom:** user accepted a Myth vs Fact angle about Rosa Parks (topic
`inspiring-women-who-changed-history`, correcting the "tired feet" myth with
her NAACP training), tapped Generate, and the returned post had no
resemblance to the accepted angle — approach label and masthead survived
unchanged, but every piece of substance (slides, caption) had pivoted to an
unrelated scenario (a Slack reply to a manager). Reported for one topic, but
suspected wider given the mechanism found below.

**Investigation:** traced the request end-to-end. Confirmed the frontend
passes the exact accepted angle/approach/mood/visual_subject through to
`/generate` unmodified (`frontend/app/generate/page.tsx`), and confirmed the
backend uses it as-is with no resampling or retry logic anywhere in
`routes/generate.py`, `angle_engine.py`, or `validator.py` — validation
failures are attached to the response as `validation_errors` but never
trigger a second generation. The actual mechanism was in the prompt itself:
`inspiring-women-who-changed-history` has `requires_citation: true`, but
`ContentBrief.sources` is unconditionally `[]` for the normal taxonomy
`/generate` flow (real `Source` objects only ever get attached via the
separate paste-link flow — no mechanism existed to attach curated sources to
a taxonomy topic). `_brief_system_prompt()` (generator.py) built a "must be
traceable to these sources" instruction that resolved to the literal string
"...none" when the source list was empty, and `critique_post()` carried a
second, separate instruction to independently verify traceability to the
same non-existent sources. Live repro with temporary debug logging on
`draft_post`/`critique_post`/`refine_post` output confirmed `critique_post()`
explicitly named citation/traceability as a "critical failure" and the
stated reason to rewrite the post.

A full scan of `topics.yaml` found 11 of 18 current topics (61%) carry
`requires_citation: true` — this is a systemic condition, not unique to the
one reported topic. Also found that `knowledge_hints` (authored per-topic,
and per its own inline comment intended to keep exactly this kind of content
honest — "biographical facts must be sourced — never invented from memory")
is used only by the cheap-tier angle-sampling call in `angle_engine.py` and
never reaches `ContentBrief` or any of the Sonnet-tier prompts — the one
mechanism that could have prevented this was silently dropped after
angle-sampling.

**Root cause:** a structural contradiction for any `requires_citation: true`
taxonomy topic — the prompt demands traceability to a source list that
never gets populated outside the paste-link flow, and no fallback grounding
was ever wired to the writing/critique stage.

**Fix:** `knowledge_hints` added to `ContentBrief` and threaded through from
`brief_builder.py`. `_brief_system_prompt()` and `critique_post()`'s citation
instructions now branch: real source-traceability language only when
`brief.sources` is actually populated (paste-link case, unchanged); a new
knowledge_hints-grounded instruction otherwise — stay within well-established
public knowledge, don't fabricate specific numbers/studies/quotes/dates,
describe patterns qualitatively when unsure of an exact figure. A startup
validation check now fails loudly if any topic has `requires_citation: true`
with empty `knowledge_hints`, so this bug class can't silently recur as the
catalog grows toward 40-60 topics.

**Verified live, before/after:** re-ran the exact Rosa Parks/NAACP Myth vs
Fact scenario end-to-end post-fix. Before the fix, `critique_post` called the
citation gap a "critical failure" and said "the entire premise of the post is
unsupportable as written" — and `refine_post` abandoned the accepted angle
for an unrelated scenario. After the fix, `critique_post` ran a "Fabricated
specifics check" instead, flagged only one soft claim ("chapter secretary for
over a decade" — an unverifiable specific duration) and explicitly called the
gendered content "specific, not generic" and the myth/fact structure
"delivered correctly." `refine_post` kept the Rosa Parks/NAACP content fully
intact and applied exactly that one surgical correction ("for over a decade"
→ "for years before that day"), with no pivot away from the accepted angle
anywhere in the pipeline.

**Considered and explicitly rejected:** hand-curating real pinned sources
(title/URL/excerpt) for all 11 affected topics — real research was actually
done for 10 of them (Pew Research, WHO, ACOG, IWPR/American Time Use Survey,
Fraley's attachment-theory overview, among others) before this direction was
reconsidered. Rejected because it solves a problem the product doesn't
actually have: the citation requirement's real purpose is stopping the model
from fabricating specifics with false confidence, not giving IG readers a
footnote trail nobody will check. Curating real sources per topic would also
not scale cleanly to 40-60 topics without becoming a standing authoring
burden. Also considered and rejected: a human-verify checkpoint gating
export for health/timely content, per blueprint Section 8 — confirmed
unnecessary since the existing preview → swipe-edit → export-to-camera-roll
→ manual-IG-post flow already functions as human review for every post, not
only health ones.

**Not a blueprint deviation** — this is a stricter-to-the-actual-intent
reading of Section 8's "never cite from memory" principle, not a departure
from it. The literal original implementation was producing a contradictory,
non-functional prompt rather than the grounding behavior the principle
actually called for; this fix makes the mechanism do what it was always
meant to do. Worth noting as a scope clarification: "citation" in this
codebase now means model-facing factual grounding, not reader-facing source
attribution — the two were conflated in the original design language.

---

## Summary — deviations from the original design docs

| # | Deviation | Why |
|---|---|---|
| 3 | Sixth slide template, `CarouselBodyTeaching`, added alongside the five locked in Phase 1 | The original `CarouselBody` single-fragment shape structurally couldn't hold real teaching content for `story`/`educational`/`framework`/`myth_vs_fact`/`common_mistakes` approaches — content kept leaking into the caption instead |
| 5 | Two Vercel domains in play (`wgs-two.vercel.app` auto-assigned default + `wgs-studio.vercel.app` canonical) instead of one clean URL | `wgs.vercel.app` was already taken globally; Vercel's auto-assigned fallback can't be removed without breaking dashboard bookkeeping |
| 8 | Login screen + RLS added | Explicit follow-up request, not in Phase 6's written "Build" list |
| 9 | Memory/brand kit actually wired to Supabase (not just schema+client existing) | Explicit follow-up request; Phase 6 as literally written stopped short of this |
| 11 | `IMAGE_QUALITY=low` instead of the doc's starting `medium` | The guide's own planned experiment, now run and confirmed |
| 12 | Frontend builds with `--webpack`, not Next 16's default Turbopack | Turbopack silently drops a file `@vercel/og` needs at runtime on Vercel; webpack doesn't |
