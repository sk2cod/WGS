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

## 15. Follow-up to #14: `validator.py`'s citation check left stale, then deployed and verified live

**Symptom (self-identified while implementing #14, not separately reported):**
`validator.py`'s `_check_citation` still read `if brief.requires_citation and
not brief.sources: return ["requires_citation is True but the brief has no
sources"]` after the #14 fix landed — meaning every knowledge_hints-grounded
taxonomy post (all 11 `requires_citation: true` topics) would now generate
correctly-grounded content but still get a false-positive
`validation_errors` entry on every single call, since `sources` is empty by
design for that path.

**Fix:** `_check_citation` now reuses `generator.py`'s `_citation_mode()`
helper and only flags a problem when the brief is grounded by *neither*
mechanism (`_citation_mode(brief) == "none"`) — the real paste-link-broken
case, or a taxonomy brief that somehow bypassed the startup loader guard
from #14. A knowledge_hints-grounded brief with empty `sources` now passes
cleanly, as intended.

**Note on scope:** considered splitting this into two separately-firing
checks (one for "sources expected but missing," one for "knowledge_hints
expected but missing," per the original ask) but didn't — with no explicit
flow tag on `ContentBrief`, both conditions reduce to the exact same
detectable state (`not sources and not knowledge_hints`); writing them as
two branches would mean one is always dead code. Implemented as one check,
documented to narrate both readings.

Tests added: knowledge_hints-mode passes clean, sources-mode (paste-link)
still passes clean and unchanged, and the real "neither present" case still
flags — with the new message text. 111/111 passing.

**Deployed and verified live in production**, not just locally: pushed to
`main` (`e2a594b`), deployed to Railway (`railway up --service
wgs-backend`), confirmed the app started successfully (implicitly
re-validating the #14 startup-loader guard against the real `topics.yaml`),
then re-ran the exact Rosa Parks/NAACP Myth vs Fact scenario as a live HTTP
call against `wgs-backend-production.up.railway.app` — `200` in 25.3s.
Content stayed fully grounded in the accepted angle end to end (cover,
both teaching-body slides, closing, and caption all correctly built around
the tired-seamstress myth vs. decade-of-NAACP-organizing fact), and
`validation_errors: []` — confirming both the #14 grounding fix and this
`validator.py` alignment work correctly together, in production, not just
against local repro scripts.

**Not a blueprint deviation** — same classification as #14; this is
completing that fix, not a new departure from the design docs.

---

## 16. Follow-up to #14: frontend `ContentBrief` type left out of sync with the backend

**Symptom (self-identified during a read-only frontend audit for the same
class of drift, not separately reported):** the #14 fix added
`knowledge_hints: list[str] = []` to the backend's `ContentBrief` Pydantic
model (`backend/app/models/brief.py`), but only backend files were touched
in that fix — `frontend/lib/api-types.ts`'s `ContentBrief` interface was
never updated to match, leaving it silently out of sync with the real wire
contract.

**Investigated first, before assuming it was a bug:** checked every place
the frontend sends a `ContentBrief` back to the backend
(`regenerateSlide`/`reshuffleImage` in `editor/page.tsx`, `generateFromBrief`
in the paste-link flow) — all of them pass through the exact object the
backend originally returned; the frontend never independently constructs a
`ContentBrief`. `lib/api.ts`'s `request()` helper does a raw `res.json() as
Promise<T>` with no field-stripping transform. Confirmed: no functional
drift bug, since TypeScript interfaces are erased at compile time and
`knowledge_hints` was round-tripping correctly through every
`JSON.stringify` call regardless of what the type declared — a
type-contract gap, not a runtime one. Also checked backend `regenerate_slide()`
(the one other text-generation path the frontend triggers) — it calls the
same shared `_brief_system_prompt()` fixed in #14, no separate citation
logic to have missed.

**Fix:** added `knowledge_hints: string[]` to the `ContentBrief` interface in
`frontend/lib/api-types.ts`, matching the backend model. Type-only change —
confirmed via `pnpm build` (clean compile, zero TypeScript errors) that
nothing in the codebase constructs a `ContentBrief` object literal that
would now be missing a required field; every consumer passes an existing
object through unmodified.

**Not a blueprint deviation** — a type-contract correction, not a behavior
or design change.

---

## 17. Neither Vercel nor Railway auto-deploy on push — confirmed, and #16 manually deployed

**Investigated on request, not a reported bug:** checked whether pushing to
`main` actually triggers a deployment on either platform, since #16 (the
`knowledge_hints` type fix) had been pushed but its deployment status
wasn't obvious.

**Vercel:** `vercel project inspect wgs` shows no "Git Repository" /
"Connected Repository" section at all — a project with GitHub auto-deploy
would list the connected repo and production branch there. `vercel git ls`
isn't even a real command (only `connect`/`disconnect` exist). `vercel ls`
showed the most recent deployment sitting 5 hours stale relative to the
`#16` push, and `vercel inspect` on it carried no git/commit metadata.
Confirmed: every Vercel deployment in this project's history has come from
a manual `vercel --prod` CLI run.

**Railway:** `railway status --json` on the active deployment shows
`"source": null` at the service level (no repo connected) and deployment
metadata of `"cliCaller": "claude_code"`, `"reason": "deploy"` — explicit
CLI-trigger fingerprints, not a webhook. Commit `92860c3` (fix #14) was
pushed at `14:53:08`, squarely inside a ~15-hour gap in the deployment
history (`00:19:38` → `15:13:54`) with zero deploy activity — conclusive
that the push itself triggered nothing. The deployment that eventually
shipped #14+#15 together only happened because of a manual `railway up`
run afterward, coincidentally close in time to both pushes.

**Consequence — a standing operational fact, not a bug:** every fix in
this project needs an explicit manual deploy step (`railway up
--service wgs-backend` for backend changes, `vercel --prod --yes` from
`frontend/` for frontend changes) after pushing. A merged/pushed commit is
not live until that manual step happens — confirmed concretely by #16
sitting un-deployed for the time between its push and this investigation.

**Then deployed #16:** ran `vercel --prod --yes` from `frontend/` on commit
`42a23f2`. Deployment `dpl_5W7JgiNQHL2vUTcXBpZM2Bs4Hw6C` — `READY`,
`target: production`. Verified both canonical domains
(`wgs-studio.vercel.app`, `wgs-two.vercel.app`) serving `200` afterward.

**Not a blueprint deviation** — an infrastructure/tooling characteristic,
not a design decision. Worth keeping in mind as a standing operational
fact for every future fix, though: `CLAUDE.md` may be worth a note on this
if it keeps causing confusion about whether a pushed fix is actually live.

---

## 18. Attempting to replace manual deploys with GitHub auto-deploy — partial success, Railway build actively failing until root directory is set

**Goal (requested on top of #17's finding):** connect the GitHub repo to
both Vercel and Railway for real auto-deploy-on-push, retiring the manual
`vercel --prod` / `railway up` workflow.

**Vercel — failed, needs one-time browser authorization.** `vercel git
connect` (both with an explicit repo URL and auto-detected from the local
remote) failed immediately: `"Failed to connect sk2cod/WGS to project...
Make sure... you have access to the repository if it's private."` The repo
is confirmed public via the GitHub API, ruling out a repo-visibility cause
— this means the "Vercel" GitHub App has never been installed/authorized on
the `sk2cod` GitHub account. That's an OAuth/App-installation step tied to
a browser session; no CLI path exists to complete it. Connection not made.

**Railway — connected via CLI, but the resulting auto-build immediately
failed.** `railway service source connect --repo sk2cod/WGS --branch main
--service wgs-backend` succeeded cleanly with no OAuth prompt (Railway's
GitHub App access was apparently already sufficient for this public repo).
Connecting a source triggers an immediate build per Railway's own CLI
documentation, and it did — deployment `ecb97538...` **FAILED**:
```
✖ Railpack could not determine how to build the app.
./
├── .claude/  ├── backend/  ├── docs/  ├── frontend/  ├── .gitignore  ├── CLAUDE.md  └── DEPLOY.md
```
Railpack scanned the repo root (this is a monorepo — `backend/` has the
actual FastAPI app) and found nothing it recognized. **No user-facing
impact** — Railway doesn't tear down a working deployment on a failed
build, so the service stayed `Online`, still serving the last successful
manual deploy (`569d412a`).

**Root directory has no CLI path on either platform.** Checked
`vercel project update --help` in full — build/dev/install-command,
output-directory, framework are all settable, Root Directory is not.
Checked `railway service source connect --help` — no such flag. The only
other Railway path found (`railway config` / `.railway/railway.ts`, an IaC
config system) requires installing a separate `railway-ts-sdk` package
first — real added scope beyond what was asked, not pursued. **Both
platforms require the dashboard for this one setting**: Vercel → Settings →
General → Root Directory → `frontend`; Railway → Service → Settings →
Source → Root Directory → `backend`.

**Current state, left intentionally incomplete pending dashboard action:**
Railway's GitHub connection is live and **will fail on every push to
`main`** until Root Directory is set there. Vercel's connection was never
established at all. Explicitly told not to test auto-deploy yet — a test
plan (empty commit + push, then check `vercel ls` / `railway deployment
list` for a real git-sourced deployment) was given for after both dashboard
steps are done, not before.

**Not a blueprint deviation** — infrastructure setup in progress, not a
completed characteristic of the system yet. Revisit this entry once both
platforms are confirmed working, since right now Railway is in a
partially-configured, actively-failing state that a future session
shouldn't mistake for "done."

---

## 19. GitHub auto-deploy — resolved: both platforms confirmed working end to end

**Closes out #18.** Dashboard steps were completed on both platforms
(Vercel: authorized the GitHub App, connected the repo; Railway: Root
Directory already fixed to `backend` in #18's own dashboard pass). Re-ran
verification from scratch rather than trusting the dashboard UI alone.

**Vercel — confirmed fully working.** `vercel project inspect wgs` now
shows Root Directory `frontend` (was `.`, the stale CLI-linking artifact
from #18). Pushed an empty test commit (`cc5d86d`) — a new deployment
appeared within 5 seconds, built successfully in 34s, and — the decisive
evidence this is genuinely git-sourced and not another manual leftover —
the alias list gained `wgs-git-main-sk2codv1.vercel.app`, a pattern Vercel
only ever creates for git-connected projects. Both canonical domains
(`wgs-studio.vercel.app`, `wgs-two.vercel.app`) served `200` after.

**Railway — trigger worked immediately, but surfaced a second, unrelated
build failure**, caught by the same empty-commit test:
```
ERROR: Invalid requirement: 'uv==': Expected end or semicolon (after name and no valid version specifier)
```
Root Directory was already correct this time — a genuinely new problem.
Investigated read-only before touching anything: no `nixpacks.toml`, no
`.python-version`, no `uv` version pin anywhere in the repo, and
`NIXPACKS_UV_VERSION` was never set as a Railway service variable — it has
always been 100% dependent on Nixpacks' own internal auto-detection.
Compared the failed build's logs against the previous successful one
(`b1d66132`, from the dashboard's own root-directory-fix rebuild): **same
Nixpacks version (v1.41.0), byte-identical repo tree** (the failing build
was an empty commit on top of the succeeding one's exact commit) — yet the
generated Dockerfile's `pip install uv==$NIXPACKS_UV_VERSION` line resolved
to a concrete version (`uv==0.4.30`) in one build and to nothing
(`uv==`) in the other, seconds apart. This matches a known Nixpacks
behavior: its Python provider resolves "latest uv" via a live external
lookup (querying `astral-sh/uv`'s GitHub releases) at build-plan time
rather than reading any pin from the repo — a call that can transiently
fail or rate-limit, unrelated to anything in this codebase or to the git
integration itself. The two prior successful manual `railway up` builds
never had this pinned either; they simply got lucky on timing, which is
exactly why it only became visible once auto-deploy started firing builds
more often.

**Fix:** set `NIXPACKS_UV_VERSION=0.4.30` as an explicit Railway service
variable — removes the external network dependency at build time entirely,
making the build deterministic regardless of GitHub API availability.
Setting it triggered an immediate rebuild (`1eccc4a4`, SUCCESS). Re-verified
properly with a fresh empty-commit push (`fe48dbe`) rather than trusting
that one rebuild: triggered `4e0c2922` within ~14 seconds, **SUCCESS**,
confirmed via `commitHash` match that it really was this commit, and via
the build log that `pip install uv==0.4.30` resolved correctly (not empty).
Backend responded `200` after.

**Both platforms now genuinely confirmed auto-deploying on push, verified
independently with real pushes and real build-log inspection, not just
dashboard status text.** The manual `vercel --prod` / `railway up`
workflow is retired for routine fixes — `DEPLOY.md` and `CLAUDE.md` updated
accordingly.

**Not a blueprint deviation** — infrastructure setup, now actually
complete. The `NIXPACKS_UV_VERSION` pin is worth remembering as a standing
fact: if a future `uv` upgrade is wanted, this variable needs updating
manually, since it's now deliberately no longer auto-detected.

**Correction, added after #20:** "retired for routine fixes" above was
premature for Railway specifically — the very next push (documenting this
entry) caused a real outage. Two clean SUCCESS builds in a row was not
enough evidence of determinism. See #20.

---

## 20. Railway auto-deploy caused a real production outage — build succeeded, runtime crashed

**What happened:** the docs-only commit closing out #19 (`b304278` —
ironically, the one claiming both platforms were confirmed reliable) was
pushed and auto-triggered a Railway build. The build succeeded cleanly:
`uv==0.4.30` installed correctly, all 64 packages present including
`uvicorn==0.51.0`. Because the build succeeded, Railway cut over to the new
container — unlike every prior build-time failure in #18/#19, which left
the working deployment running untouched. The new container then
**crashed on start**: `uvicorn: command not found`. Production was down
until manually recovered.

**Root cause not confirmed.** The generated Dockerfile's PATH fix
(`RUN printf '\nPATH=/opt/venv/bin:$PATH' >> /root/.profile`) only affects
login shells; if Railway's start-command execution doesn't source
`/root/.profile`, `uvicorn` would never be found regardless of installing
correctly — but this exact same Dockerfile recipe had produced a *working*
container (`4e0c2922`) only six minutes earlier, from a different commit.
Byte-for-byte comparable build steps, different runtime outcome — the same
*category* of non-determinism as #19's `NIXPACKS_UV_VERSION` issue, but
this time affecting something that isn't pinnable via a simple service
variable. Not investigated further per explicit instruction to hold off on
more test pushes before this is understood — every push right now is a
real deploy attempt against a live production service.

**Recovery, and a second problem discovered along the way:** `railway
redeploy` was ruled out (would only re-run the same crashed image, not
rebuild). Tried `railway up` from `backend/` (the directory manual deploys
had always run from throughout this session) — **that failed differently**:
`Failed to read app source directory`. Root cause: with `Root Directory:
backend` now configured on the service (set in #18 for the git
integration), a manual CLI upload from *inside* `backend/` uploads that
folder as the app root, and Railway then looks for a doubly-nested
`backend/backend/...` that doesn't exist. This is a real, newly-introduced
side effect of connecting the git integration — manual deploys must now
run from the **repo root**, not `backend/`, as long as Root Directory stays
configured. Re-ran `railway up` from the repo root — succeeded, service
restored, confirmed `200` on `/topics`.

**Immediate mitigation:** reverted the "auto-deploy is the reliable primary
workflow, retire manual deploys" framing in `DEPLOY.md` and `CLAUDE.md`
(written in #19, proven wrong within minutes) back to "keep using `railway
up` for the backend" until this is root-caused, while leaving Vercel's
auto-deploy status as reliable (no equivalent failure observed there).
Also documented the repo-root gotcha for manual deploys in both files, since
it's now a standing behavior change, not a one-off.

**Not a blueprint deviation** — infrastructure reliability finding, not a
design decision. **This entry supersedes #19's closing claim.** Anyone
reading #19 alone would believe Railway auto-deploy is safe to rely on; it
is not, as of this entry. Do not re-enable "auto-deploy is primary" framing
for Railway without either root-causing the PATH issue or observing enough
consecutive clean auto-deploys (through real work, not synthetic test
pushes) to justify confidence — the sample size that led to #19's
conclusion (two successes) was not enough.

---

## 21. Two safety fixes applied for #20, not yet deployed

**`build.watchPatterns: ["/backend/**"]`** added to `backend/railway.json` —
scopes Railway's auto-deploy trigger to actual backend changes, so a
docs-only commit (exactly what caused #20) can no longer trigger a backend
rebuild at all. Confirmed via Railway's live `railway.schema.json` (fetched
directly, not assumed) and its own docs that `watchPatterns` are
**repo-root-relative even when Root Directory is set** — a bare
`"backend/**"` without the leading slash, or assuming root-directory
relativity, would have been silently wrong.

**`deploy.healthcheckPath: "/topics"` + `healthcheckTimeout: 60`** also
added — makes Railway verify a new deployment actually responds before
routing production traffic to it, instead of cutting over the instant the
build succeeds. This is the direct fix for #20's actual failure mode (build
succeeded, runtime crashed, traffic still cut over) — a crashing container
should now get caught before it ever goes live, falling back to "keep
serving the last good deployment," matching the safe behavior already seen
on every build-*time* failure.

Both confirmed as valid JSON and against the schema; full test suite still
111/111. **Committed locally only, deliberately not pushed** — pushing is
itself a live deploy trigger against production right now, and verifying
these two fixes are correct before the next one happens is the entire
point.

**Not a blueprint deviation** — infrastructure hardening in direct response
to #20.

---

## 22. #21's health-check gate confirmed working on a real recurrence — no outage this time

**Pushed the three local commits from #21.** The resulting deployment
(`52303bf6`) hit the **exact same `uvicorn: command not found` bug as
#20** — third occurrence now, still not root-caused, still non-deterministic
against an identical-looking build recipe. This time, the outcome was
different:

```
Starting Healthcheck — Path: /topics, Retry window: 1m0s
Attempt #1-4 failed with service unavailable
1/1 replicas never became healthy! Healthcheck failed!
```

Railway marked the deployment `FAILED` and **did not cut over traffic**.
Confirmed directly rather than assumed: `curl` on the production URL
returned `200`, and `railway status` showed `Online · Deploy failed` — the
previous good deployment (`d5b0caf2`) kept serving throughout. Zero
user-facing impact, versus #20's real outage from the identical underlying
bug.

**Status going forward:** the `uvicorn` PATH issue is still unresolved and
will keep failing new backend deploys until root-caused — but it's now
contained rather than dangerous, which was the actual goal of #21. Worth
root-causing when there's appetite for it (leading candidate: the Dockerfile's
PATH fix lives in `/root/.profile`, which only applies to login shells, and
whatever different shell context Railway sometimes uses to run the start
command doesn't source it) — but no longer an active production risk in
the meantime.

**Not a blueprint deviation** — confirms infrastructure hardening already
logged in #21 actually holds under a real failure, not synthetic testing.

---

## 23. Root-caused #20/#22's `uvicorn` crash — and the vendor's own diagnosis was wrong

**Railway's own platform diagnosis** (surfaced independently, not asked for)
proposed: Nixpacks installs `uvicorn` into `/opt/venv`, but only adds it to
`PATH` via `/root/.profile`, which the non-login start shell never sources.
Proposed fix: hardcode `startCommand` to the absolute path
`/opt/venv/bin/uvicorn`.

**Verified against actual build logs before applying anything, per explicit
instruction — and the diagnosis didn't hold up.** Checked all three real
crashes (`8b10817e` from #20, `52303bf6` from #22) against a known-good
build (`d5b0caf2`). Every single crash showed a warning the successful
builds never showed:
```
warning: `VIRTUAL_ENV=/opt/venv` does not match the project environment path `.venv` and will be ignored
Creating virtual environment at: .venv
Installed 64 packages in ...ms
```
This means `uv sync` wasn't just failing to expose `/opt/venv` on `PATH` —
in every crash, **it never installed anything into `/opt/venv` at all.** It
detected a mismatch, discarded the pre-activated `/opt/venv`, and installed
all 64 packages (including `uvicorn`) into a separate `/app/.venv` instead.
Hardcoding `startCommand` to `/opt/venv/bin/uvicorn`, as suggested, would
not have fixed any of the three actual crashes observed — it would have
converted `uvicorn: command not found` into
`/opt/venv/bin/uvicorn: No such file or directory` in the identical
failure scenarios, since that path was never populated in any of them.
The real inconsistency sits one level upstream of where the vendor's
diagnosis pointed: whether `uv sync` respects the activated venv at all,
not what happens to `PATH` afterward.

**Fix:** pinned `UV_PROJECT_ENVIRONMENT=/opt/venv` as a Railway service
variable, forcing `uv sync` to always target `/opt/venv` regardless of its
own mismatch heuristic — confirmed via Railway's docs and the project's own
prior build logs (`ARG`/`ENV "ANTHROPIC_API_KEY"` already visible in
generated Dockerfiles from a plain service variable) that this is exposed
during the Nixpacks build step, not just at runtime — no `railway.json`
change needed.

**Verified the actual mechanism, not just a green deployment:** the next
build's logs showed the mismatch warning **absent** — straight from
`Successfully installed uv-0.4.30` to `Prepared 1 package` to
`Installed 64 packages`, no separate `.venv` created. Runtime logs showed a
clean `Uvicorn running on http://0.0.0.0:8080` and a real `200` on the
health check's own `GET /topics`. Confirmed independently: `railway status`
showed the new deployment ID genuinely `Online` (not a health-check
fail-safe fallback to the previous one), and a direct `curl` against the
production URL returned `200`.

**Not root-caused further:** *why* `uv sync`'s mismatch check fires
inconsistently in the first place (a leading theory, not confirmed: the
shared `--mount=type=cache` uv cache persisting project-environment state
across builds) is now moot — forcing the variable removes the ambiguity
regardless of why `uv` was inconsistent about it.

**Not a blueprint deviation** — bug fix, and a correction of a third
party's own diagnosis of its platform, not a design decision. Worth
remembering: don't apply a vendor's proposed fix on their word alone when
the actual evidence (real build logs, in this case) is checkable and cheap
to check — it directly contradicted the suggested fix here.

**Closing-the-loop confirmation:** pushing this very entry (`d2ab3b3`,
docs-only — `CLAUDE.md`/`DEPLOY.md`/this file, nothing under `backend/`)
came back `SKIPPED` on Railway, not a wasted rebuild — `watchPatterns`
from #21 holding correctly alongside this fix, not just at the moment it
was first set. Production `curl` still `200` throughout.

---

## 24. "The quota has been exceeded" on Generate — a client-side sessionStorage bug, not an LLM provider issue

**Symptom:** on mobile (real device, not simulator), tapping Generate after
accepting a proposed angle failed **every single time** with "The quota has
been exceeded." Reported alongside explicit confirmation that both Anthropic
and OpenAI dashboards showed available credits, ruling out the obvious
reading of the message.

**Investigation, read-only first per instruction:** a repo-wide grep found
zero hardcoded "quota" text anywhere in the codebase — the string wasn't
coming from any WGS error-handling path, ruling out a deliberate
rate-limit/billing message from the app itself. Direct backend/provider
calls (Anthropic, OpenAI) couldn't reproduce it. The user then gave a
precise repro: Career category → "Negotiating Your Worth" (a carousel,
therefore a real GPT Image 2 hero image) → accept → Generate → crash.

**Root cause:** `frontend/lib/session-store.ts`'s `saveCurrentPost()` wrote
the entire `/generate` response — including `hero_image_base64`, a
multi-MB base64-encoded string — into `sessionStorage.setItem()` with no
try/catch. Mobile Safari enforces a much smaller per-origin storage quota
than desktop browsers; writing a multi-MB string past it throws a real,
uncaught `QuotaExceededError` DOMException, whose exact WebKit message text
is "The quota has been exceeded." This happens *after* the Anthropic/OpenAI
calls have already succeeded — the error is a pure client-side storage
failure surfacing through the UI's generic error handling, unrelated to any
provider's actual quota or billing state. Desktop browsers' larger quotas
had masked this throughout development.

**Fix:** `hero_image_base64` no longer goes into `sessionStorage` at all —
it's held in an in-memory module-level variable (`cachedHeroImage`) instead.
`saveCurrentPost()` writes the rest of the response (text-only, small) to
`sessionStorage` with the hero field explicitly nulled out; `loadCurrentPost()`
reassembles the full object by splicing the in-memory value back in. The
`sessionStorage.setItem()` call is also now wrapped in try/catch (covers the
remaining edge case of an already-near-full quota, e.g. Safari Private
Browsing's ~0 effective quota) — degrades to in-memory-only rather than
crashing. Tradeoff, accepted: the hero image is lost on a hard page reload
mid-flow (module state doesn't survive that), where before this fix the flow
never completed at all on mobile Safari.

**Verified in a real browser (Playwright), not just a clean build:** ran the
full login → browse → accept angle → Generate → editor → export flow
against a local dev stack (dev server + local backend, to avoid CORS from
hitting production's `FRONTEND_ORIGIN` allowlist). Confirmed: (1) the flow
completes with zero console errors, where it previously crashed at Generate;
(2) the hero image genuinely renders in both the editor and export screens
(visually confirmed via screenshot — an automated `<img src="data:...">` DOM
check returned a false negative, since `SlideRenderer` paints the hero as a
CSS background rather than an `<img>` tag, not a real absence); (3)
`sessionStorage`'s `wgs-current-post` key is now 2687 bytes with
`hero_image_base64: null` explicitly present, confirming the fix is actually
taking effect and not coincidentally not crashing on this particular test
payload.

**Not a blueprint deviation** — `implementation-guide.md`'s "client holds
the brief" round-trip pattern (used elsewhere for
`/generate/regenerate-slide` and `/generate/reshuffle-image`) is unchanged;
this only narrows *where* the hero image specifically lives during that
round-trip, since the original design didn't anticipate mobile Safari's
storage ceiling.

---

## 25. Browse screen rebuilt: category-first (strict `primary_category`) replaces the flat multi-tag list — deliberate deviation from blueprint.md Section 5

**What changed:** `frontend/app/page.tsx`'s "Browse all topics ▼" flat list (every
topic in one scrollable list, single toggle) was replaced with a two-step flow:
a fixed grid of exactly 7 category tiles (`Mindset`, `Career`, `Wellness`,
`Women's Health`, `Relationships`, `Society`, `Inspiring Women` — hardcoded in
`page.tsx`, not derived from `topics.yaml`), and tapping one reveals only the
topics whose `Topic.primary_category` exactly matches that tile. There is no
flat/unfiltered browse view anymore — the category tiles are the only entry
point. Filtering uses `topic.primary_category === selectedCategory` only;
`topic.categories` (the multi-tag list) is not read by this screen at all.
Everything downstream of tapping a topic (`goToGenerate(topic.id)`, the
`/generate` route, `brief_builder.py`, masthead computation) is unchanged —
confirmed via `git diff --stat`, which shows only `frontend/app/page.tsx`
touched.

**Why — deliberate deviation from blueprint.md Section 5:** the blueprint's
original browse design has a topic show up under every one of its `categories`
tags (a multi-tag display — "every benefit of a graph, no graph infra"). After
review, strict `primary_category`-only browsing was chosen instead: the
masthead already counts and labels every post against exactly one category
(`Topic.primary_category`, Section 11/12), so a browse screen that could show
the same topic under multiple tiles would let her find and generate a topic
from a category tile that doesn't match what the resulting post's masthead
will actually say — e.g. finding "Setting Boundaries Without Guilt" under a
`Relationships` tile (it's tagged `["Mindset", "Relationships"]`) but getting a
`WGS — MINDSET NO. n` masthead on the generated post. Strict primary-category
browsing keeps the category she browsed under and the category the post is
labeled with always consistent. `Topic.categories` is kept as-is in the
Pydantic model/YAML (not removed) — only this screen's logic ignores it.

**Verified manually** (not phase-gated — this isn't one of the six original
phases): `pnpm exec tsc --noEmit` clean; grepped `primary_category` values
across all 18 current `topics.yaml` entries — distribution is Mindset 3,
Career 3, Wellness 3, Women's Health 3, Relationships 3, Society 2, Inspiring
Women 1 (sums to 18), and every value exactly matches one of the 7 hardcoded
tile labels, so every topic appears under exactly one tile and none are
orphaned.

---

## 26. `single_image` generation crashing on certain approaches — approach sampled before format is known

**Symptom:** generating a `single_image` post could fail with a hard parse
error (`ValueError: expected 1 slide(s) (['single_stat']), got [...]`) —
the model returned multiple slide-like objects (with off-schema
`template_id`s like `checklist`, `myth_fact`, `tip`, or several
`single_stat` objects labeled `STEP 1`–`STEP 4`) instead of the one slide
`single_image` requires. First surfaced while testing the (separately
in-flight, not yet committed as of this entry) 37-pair taxonomy
replacement, then investigated and confirmed as a pre-existing,
taxonomy-independent bug — reproducible against the old 18-topic taxonomy
just as easily (see the isolated regression check below).

**Investigation:** traced the sampling call chain read-only before
changing anything. `angle_engine.py`'s `sample_cell()`/`generate_angle()`
picks an approach purely from `topic.seed_angles × APPROACHES (all 8) ×
ENTRY_POINTS` — `format` was never a parameter anywhere in that file.
`format` is known to the caller (`routes/generate.py`'s `run_generate()`,
which receives it as a plain argument) at the exact same point
`generate_angle()` gets called, but the plumbing simply never passed it
down; `format` was only used afterward, in `brief_builder.py`, to compute
`slide_count` — by then the approach was already irreversibly sampled.
`generator.py`'s `slide_roles_for()` collapses `single_image` to exactly
one slide role (`single_quote` for the poetic register, `single_stat` for
the direct register) regardless of which approach got sampled.

Deliberately tested all 8 approaches forced onto `single_image` (multiple
live `/generate` trials per approach, not assumed from reading the code):
`checklist`, `myth_vs_fact`, and `framework` reliably crashed — each has a
`_APPROACH_DEFINITIONS` entry (`generator.py`) that explicitly demands
multiple distinct sub-items (an "enumerable set," "distinct labeled
parts," or a separate myth + fact), which cannot compress into
`single_stat`'s one kicker/number/supporting-line. `educational` crashed
intermittently (1 of 4 trials — same multi-step tendency, less reliably
triggered). `common_mistakes`, `stat_research`, `story`, and
`question_reflection` never crashed across 4 trials each — structurally
closer to "one fact/moment + one interpretation," which fits the 1-slide
shape.

**Root cause:** approach gets sampled with no knowledge of format, so
nothing stops the sampler from picking an approach whose own structural
definition is incompatible with `single_image`'s hard 1-slide ceiling.

**Fix — Python-side, deterministic, no LLM prompt or slide template
changes:**
- `taxonomy/approaches.py`: added `SINGLE_IMAGE_SAFE_APPROACHES` — the 4
  approaches confirmed safe by live testing (`common_mistakes`,
  `stat_research`, `story`, `question_reflection`), as a named constant
  next to `APPROACHES`/`TEACHING_BODY_APPROACHES`, not an inline list
  buried in the sampler.
- `angle_engine.py`: `sample_cell()`/`generate_angle()` now take an
  optional `format` parameter; when `format == Format.SINGLE_IMAGE`, the
  candidate pool is built from `SINGLE_IMAGE_SAFE_APPROACHES` only,
  otherwise (including `format=None`) from the full `APPROACHES` list —
  unchanged behavior for carousel and for the one caller that doesn't
  know format yet (`selector.py`'s `build_daily_pick()`, which
  precomputes only a hook + thumbnail before a format is chosen — left
  passing no `format`, so it stays unrestricted, matching current
  behavior).
- `routes/generate.py`: both call sites that already had `format` in
  scope (`propose()` and `run_generate()`) now pass it through to
  `generate_angle()`. `propose()` matters as much as `run_generate()`
  here — it's what actually populates the `preselected` angle a real
  client accepts and later replays into `/generate`, so constraining it
  too means a real client can never end up with an unsafe
  approach+`single_image` pairing via the normal accept flow.

**Verified:**
- Deterministic pool-membership check: none of `checklist`/`myth_vs_fact`/
  `framework`/`educational` appear in any topic's `single_image` candidate
  pool; 500 sampling trials across seeds 0–499 with `format=SINGLE_IMAGE`
  never produced anything outside the 4 safe approaches.
- Forcing the 4 excluded approaches directly via `preselected` (bypassing
  the sampler on purpose, the same method used to find the bug) still
  reproduces the original crash for at least one of them in a single
  trial — confirming the fix constrains the *sampler*, not the
  generation path itself, exactly as scoped.
- 6 real, unforced `/generate` calls across different topics on
  `single_image` with the new pool — 0 crashes, 0 validation errors,
  every sampled approach drawn from the safe set.
- Carousel format re-verified unrestricted: 200 sampling trials still
  reach all 8 approaches; real `/generate` calls forcing `checklist` and
  `framework` onto carousel both completed normally (3–4 slides, only
  unrelated minor validation findings — a forbidden-phrase hit and a
  word-count overage).
- Isolated regression check: stashed the (separately in-flight, not yet
  committed) topics.yaml replacement and ran the full suite against the
  *old* taxonomy with only this fix applied — **111/111 passing**,
  confirming zero regressions from this change on its own (one test
  helper, `test_generate_route.py::_single_image_draft_for_seed`, needed
  a one-line update to pass `format=Format.SINGLE_IMAGE` into its own
  `sample_cell()` call so it predicts the same approach the real
  now-constrained path will sample for a given seed — a direct,
  necessary consequence of this fix, not unrelated drift).

**Not a blueprint deviation.** Consistent with blueprint decision 3 —
"Python owns the brief and its constraints; the LLM generates inside it"
— slide shape was already Python-decided and deterministic
(`slide_roles_for`); this fix makes the *approach selection* upstream of
it respect that same constraint instead of leaving Python and the model
to independently discover the conflict downstream, one crashed request at
a time.

---

## 27. Taxonomy replacement (37 pairs) broke `awareness_calendar.py` and 8 test files — caught before push, not in production

**Symptom:** replacing `topics.yaml` with the new 37-pair taxonomy
(logbook entry above this one covers the sampling fix; the taxonomy swap
itself was built and verified for loader-validity and live `/generate`
correctness in an earlier session, but the full test suite was never run
against it at that point). Running `pytest` after the swap surfaced
**51 of 111 tests failing** — traced every one before touching anything:
all were either `KeyError: Unknown topic_id` from fixtures hardcoding old
topic ids (e.g. `mindset-reframing-self-doubt`, `career-salary-negotiation`)
across 8 test files, or stale count assertions (`assert len(topics) == 18`,
`assert 15 <= len(topics) <= 20`, `assert 3 <= len(topic.seed_angles) <= 5`
— the last one broken by design, since 3 approved Wellness pairs carry 6
seed phrases verbatim from `taxonomy-draft-v1.md`).

**A real production bug, not just test staleness:** `app/sources/
awareness_calendar.py`'s `AWARENESS_DAYS` list hardcodes a `related_topic_id`
per awareness day, read by `select_daily_picks`/`build_daily_pick` to
resolve a real `Topic` for the timely daily-pick slot. 5 of its 8 entries
pointed at topic ids the new taxonomy no longer has (Galentine's Day,
Equal Pay Day, World Health Day, Menstrual Hygiene Day, International
Self-Care Day) — this was production code, not a fixture, and would have
failed a real `get_topics_by_id()` lookup the next time one of those 5
dates actually came due. `test_awareness_calendar.py`'s own
`test_all_related_topic_ids_exist_in_taxonomy` caught this immediately on
the first post-swap test run, before any of it reached production.

**Root cause:** the taxonomy-replacement session verified the loader,
manual `/generate` calls, and the browse-screen tile counts, but never ran
`pytest`, so neither the test fixture staleness nor the
`awareness_calendar.py` bug surfaced until this session explicitly ran the
full suite as part of verifying an unrelated fix.

**Fix:**
- `app/sources/awareness_calendar.py`: remapped the 5 stale
  `related_topic_id` values to their closest new-taxonomy equivalent
  (`relationships-friendship-boundaries` → `relationships-boundaries`,
  `society-gender-pay-gap` → `society-pay-scale`,
  `health-reproductive-literacy` → `health-reproductive-health`,
  `health-hormonal-cycle-basics` → `health-hormonal-cycle`,
  `wellness-rest-is-not-lazy` → `wellness-rest`); the other 3
  (`inspiring-women-who-changed-history`, `wellness-stress-regulation`,
  `career-imposter-syndrome`) already matched unchanged ids in the new
  taxonomy and needed no change.
- 8 test files (`test_angle_engine.py`, `test_brief_builder.py`,
  `test_generate_route.py`, `test_generate_route_http.py`,
  `test_generator.py`, `test_main.py`, `test_selector.py`,
  `test_taxonomy.py`, `test_validator.py`) updated to reference real
  topic ids in the new taxonomy and correct counts.

**Verified:** functional check (not just the id-existence test) —
`upcoming_awareness_days(date(2026, 2, 10), window_days=7)` resolves
Galentine's Day to `relationships-boundaries` → "Boundaries" end to end.
Full suite: 111/111. Deployed to Railway (commit `0e5b66e`) and confirmed
live: build log shows no stale-venv warning, healthcheck passed on the
first attempt, `GET /topics` on the production URL returns 37 topics with
the correct per-category distribution.

**Not a blueprint deviation** — a bug fix, caught pre-push by finally
running the existing test suite against the swap, not a design decision.
Worth remembering as a process note: a taxonomy/data-shape change needs
`pytest` run against it, not just loader-validity and spot-checked live
calls, before it's considered verified.

---

## 28. Single Image style choice: "Poetic Quote" / "Quick Stat" — additive, on top of #26's approach-pool fix

**What this adds:** #26 fixed `single_image` crashing on structurally
incompatible approaches by constraining the sampler to a 4-approach safe
pool (`common_mistakes`, `stat_research`, `story`, `question_reflection`)
when format is `single_image` — but which of those 4 gets sampled was
still random, meaning she couldn't reliably choose "a quote-style post" vs.
"a stat-style post" up front. This gives her that choice directly, on top
of #26's fix rather than instead of it:

- `taxonomy/approaches.py`: split `SINGLE_IMAGE_SAFE_APPROACHES` into
  `SINGLE_IMAGE_QUOTE_APPROACHES` (`story`, `question_reflection` — the
  poetic-register half, `single_quote` template) and
  `SINGLE_IMAGE_STAT_APPROACHES` (`common_mistakes`, `stat_research` — the
  direct-register half, `single_stat` template). `SINGLE_IMAGE_SAFE_APPROACHES`
  itself is now defined as their union and kept fully intact for every
  existing no-style-given caller.
- `angle_engine.py`: `sample_cell()`/`generate_angle()` gain an optional
  `single_image_style: Literal["quote", "stat"] | None` parameter. When
  `format == single_image` and a style is given, the pool narrows to just
  that half; when format is `single_image` and no style is given, behavior
  is unchanged from #26 (samples the full 4-approach safe pool); when
  format isn't `single_image`, the parameter has no effect at all (full 8
  approaches, exactly as before this change).
- `routes/generate.py`: `ProposeRequest` and `GenerateRequest` both gain
  `single_image_style: Literal["quote", "stat"] | None = None`. Both
  `propose()` and `run_generate()` thread it through to `generate_angle()`
  — `propose()` matters as much as `run_generate()` for the same reason
  #26 called out: it's what populates the `preselected` angle a real
  client later replays into `/generate`, so the style choice has to hold
  at the point she actually picks it, not just at final generation.
- Frontend (`app/generate/page.tsx`): when Single Image is the selected
  format, a second row of two buttons appears — "Poetic Quote" / "Quick
  Stat" — reusing the existing `primaryButtonStyle`/`secondaryButtonStyle`
  toggle pattern already used for the Carousel/Single Image choice
  directly above it. Defaults to "Poetic Quote" selected. The choice is
  wired into both the `/generate/propose` and `/generate` request bodies
  (`lib/api.ts`, `lib/api-types.ts`); Carousel format shows no such choice
  and never sends the field a non-null value.

**Verified:**
- 6 real, unforced `/generate` calls on `single_image` + `style=quote`
  across different topics — 100% produced `single_quote` slides, approach
  always `story` or `question_reflection`, 0 crashes (one transient
  strong-tier JSON-parse hiccup on one call, the pre-existing intermittent
  class from logbook #7 — succeeded cleanly on retry, unrelated to this
  change).
- 6 real, unforced `/generate` calls on `single_image` + `style=stat` —
  100% produced `single_stat` slides, approach always `common_mistakes` or
  `stat_research`, 0 crashes (two unrelated minor validator findings — a
  word-count overage, a forbidden-phrase hit — normal validator behavior,
  not a citation/grounding or shape problem).
- Deterministic pool-membership checks (no LLM calls): 500 trials with no
  style given still reach exactly the same 4-approach pool as #26; 200
  trials each with `style=quote`/`style=stat` never leave their respective
  2-approach half.
- HTTP-level check via `TestClient` against the real `/generate/propose`
  route: a request with the `single_image_style` field omitted entirely
  (simulating an old/cached frontend build) returns `200` and samples from
  the full safe pool, exactly as before this field existed — confirms the
  change is additive, not breaking, for any client that hasn't picked up
  the new frontend yet.
- Carousel: 300 trials each with `single_image_style` set to `None`,
  `"quote"`, and `"stat"` all reached the identical full 8-approach set —
  confirms the field is inert outside `single_image`, regardless of value.
- `pnpm exec tsc --noEmit`: clean.
- Full backend suite: **111/111 passing**.

**Not a blueprint deviation** — additive new scope built directly on
#26's already-fixed approach-pool constraint (narrowing an existing safe
pool further by explicit choice, not reintroducing anything #26 excluded
for structural reasons), not a departure from anything locked in
`blueprint.md`/`implementation-guide.md`.

**Follow-up, investigated on direct request: which call hit the transient
JSON-parse failure seen during this entry's live testing, and does it
close #13's open question?** Re-ran 20 additional live `single_image`
`/generate` calls (10 `quote`, 10 `stat`, across 10 different topics) with
full traceback capture, not just the exception type name. **5 of 20
failed** — a real, measurable rate, higher than the single incidental
hiccup in the main testing above suggested. All 5 traces are identical in
shape: `generate_post` → `refine_post` → `_parse_post` — **never**
`draft_post`, **never** `critique_post`. Since `refine_post` only runs
after `critique_post` returns successfully, all 5 cases are also positive
evidence `critique_post` completed cleanly every time this session
(partial progress on #13's "only `draft_post` was directly repro-tested"
gap — `critique_post` now has real, if indirect, live coverage).

**But this is not a clean confirmation that "the #7 fix also covers
`refine_post`"**, and it would be inaccurate to log it that way. #7's
original signature was an *empty* response — extended thinking consuming
the entire token budget, `stop_reason: max_tokens`, a `thinking` content
block only, no text at all. None of these 5 failures look like that. Two
were literal JSON syntax errors on substantial, real content (`Extra
data: line 1 column 356` — a complete JSON object followed by trailing
data; `Invalid control character at: line 1 column 401` — an unescaped
raw character inside a string). The other three were `refine_post`
returning 5–8 slide objects for a brief whose `slide_count` is 1 — the
same "too many items" symptom #26 fixed at the sampling layer, except
here the *approach* was already a confirmed-safe one (`story`,
`question_reflection`, `common_mistakes`) and `draft_post` had already
returned the correct single slide for the exact same brief moments
earlier — `refine_post`'s own rewrite is where it drifted. Both failure
shapes involve substantial, real content, not an empty response, so they
don't carry #7's specific fingerprint one way or the other without
inspecting the raw `stop_reason` (not captured here).

**Net finding:** `critique_post` gets real supporting evidence of
reliability from this session's volume; `refine_post` does not — it has
its own, separate, still-open reliability gap (occasional malformed JSON
syntax, or disregarding the 1-slide constraint independently of approach
safety), observed at roughly 1-in-4 in this sample. Worth a dedicated
look given that rate, but out of scope for #28 itself — not chased
further here.

---

## 29. OPEN — `refine_post` intermittent JSON/shape failures, ~1-in-4 in a 20-trial sample — not yet fixed

**Status: open, carried forward for a dedicated session — same pattern as
#13's carried-over items. No fix attempted here.**

**Symptom:** during live testing for #28 (the Single Image style choice),
a 20-trial batch of real `single_image` `/generate` calls (10 `quote`
style, 10 `stat` style, across 10 different topics) hit **5 failures** —
a measurable ~1-in-4 rate, not a rare fluke. Every failure traced to the
same call: `generate_post` → `refine_post` → `_parse_post`. Full detail
and tracebacks are in #28's follow-up section; this entry exists so the
issue has its own standalone record rather than staying folded into an
unrelated feature entry.

**Root cause, as currently understood:** `refine_post`'s rewrite step
either (a) returns JSON with a genuine syntax error on otherwise
substantial, real content — observed: `Extra data` after a complete JSON
object, and an unescaped raw control character mid-string — or (b)
returns more slide objects than the brief's `slide_count` allows (5–8
slide objects for a `single_image` brief that only ever wants 1), even
though the sampled approach was already one of the confirmed-safe ones
(`story`, `question_reflection`, `common_mistakes`) and `draft_post` had
already returned the correct single slide for the exact same brief
moments earlier. So the drift happens specifically during refinement, not
because of an unsafe approach reaching `refine_post` (logbook #26 already
rules that out) and not because the shape was ambiguous going in.

**Explicitly distinct from #7's original signature:** #7's bug was an
*empty* response — extended thinking consuming the entire token budget,
`stop_reason: max_tokens`, a `thinking` content block only, no text at
all. None of these 5 `refine_post` failures look like that — all involved
substantial, real content that was merely malformed or excessive. The
`thinking: disabled` fix from #7 is not implicated one way or the other
here without inspecting the raw `stop_reason` on a failing call, which
wasn't captured in this batch.

**What's confirmed, not just suspected:** `critique_post` is reliable —
in all 5 of these failing trials, `critique_post` necessarily ran and
returned a usable critique successfully before `refine_post` broke on the
next step (`generate_post`'s draft → critique → refine sequence means
`refine_post` is only reached after `critique_post` returns). This is
real, if indirect, live evidence for `critique_post`'s reliability, on
top of #13's original open question about it.

**Not fixed here — deliberately.** Worth a dedicated session: candidates
worth checking first would be whether `refine_post`'s prompt reinforces
the exact slide-count/role constraint as strongly as `draft_post`'s does,
and whether capturing the raw Anthropic response (`stop_reason`, content
block types) on a live repro would rule the `thinking` mechanism in or
out definitively rather than by inference.

---

## 30. Fixing the read-only investigation's three findings: workplace-drift voice samples, a leading `_SPECIFICITY_INSTRUCTION` example, and a hero-image cache collision

A prior read-only investigation (this same session, before any fix) traced
Report A's content drift (accepted angles about rest/fatigue/body-kindness
generating workplace-meeting content instead) to three mechanisms. This
entry fixes all three, verified with real Anthropic/OpenAI API calls
against a local, file-backed `MemoryStore` (never against production
Supabase — see "Verified" below for why that distinction matters here).

### Fix 1 — `voice_samples.direct` was uniformly workplace-themed (dominant driver)

**Root cause (already established by the read-only trace):** `myth_vs_fact`,
`educational`, `checklist`, `stat_research`, `framework`, and
`common_mistakes` (6 of 8 approaches) all resolve to the brand kit's
"direct" voice register (`taxonomy/voice_register.py`). All 5 of that
register's original samples were workplace/career-themed (meetings,
salary negotiation, workload, "no one has to guess" boundaries-at-work).
`_brief_system_prompt` (`generator.py`) injects these verbatim as few-shot
examples on every draft/critique/refine call — the model was found to be
pattern-matching to their *topic domain*, not just their tone, and
inventing an office scene regardless of what the actual accepted angle
was about.

**Fix:** rewrote `voice_samples.direct` (`taxonomy/wgs_brand_kit.py`) —
same count (5), same grounded/direct/confident tone and rhetorical
patterns as the originals, but domain-diverse: one sample each from
Wellness, Women's Health, Relationships, Society, and Mindset, none
anchored in a meeting, manager, workplace, or office scene. `poetic`
samples were untouched (they were never the reported failure mode, and
the read-only trace already established they draw from a different,
non-work-themed set).

**This is a deliberate deviation from a value blueprint.md calls
"Locked"** (Section 4) — logged as such, not silently overwritten.
`docs/blueprint.md` Section 4 and `docs/implementation-guide.md`'s copy of
`WGS_BRAND_KIT` were both updated to match, with an inline note pointing
back here, so the docs don't silently drift from what the app actually
runs (the failure mode logbook #16 flagged for a different field).
`frontend/lib/wgs-brand-kit.ts` was also updated for consistency — it's a
verbatim "Locked value" copy per its own header comment, used only for
`/preview` and exercising `/api/render` before real generation exists, so
it never touches the actual generation pipeline, but leaving it stale
would have recreated the exact doc-drift problem this fix is trying to
avoid elsewhere.

**Important caveat — the live Supabase `brand_kit` row was deliberately
NOT touched.** `taxonomy/wgs_brand_kit.py`'s `get_brand_kit()` only seeds
Supabase from this constant if the `brand_kit` table is empty; production
seeded it long ago (logbook #9), so editing the Python constant alone
has **no effect on production** until the live row is also updated (there
is no existing "edit brand kit" route/mechanism — `engine/memory.py`'s
`append_voice_sample()` explicitly says persisting a `BrandKit` update
isn't wired up yet). Given the explicit instruction not to let this go
near production before review, this was left as an open follow-up rather
than done unilaterally: the constant and docs are fixed, but production's
actual `direct` voice samples are still the old, workplace-themed ones
until someone runs `upsert_brand_kit()` (or the Supabase row is edited
directly) with the new value.

### Fix 2 — `_SPECIFICITY_INSTRUCTION`'s literal example nouns (compounding factor)

**Root cause:** the instruction told the model to ground posts in "a
specific meeting, a specific text message, a specific conversation" —
illustrative examples that the model appears to have pattern-matched to
literally, not just as illustrations of "be concrete." Compounded Fix 1
rather than being an independent cause on its own.

**Fix (`generator.py`):** reworded to name the *quality* of specificity
wanted rather than domain-specific nouns — "a specific sensation, a
specific moment in her day, a specific interaction with someone in her
life" — plus an explicit line telling the model to let the scene come
from wherever the angle is actually grounded ("her body, her home, a
friendship, a quiet moment alone — not... a default assumption about
where she spends her time"). No example noun in the new wording implies
an office/work setting.

**Not a blueprint deviation** — this is a prompt-wording bug fix, not a
locked-spec change; blueprint.md never specified this instruction's exact
example nouns.

### Fix 3 — hero image cache collision across different angles on the same topic

**Root cause (already established by the read-only trace):** the hero
image cache keyword (`providers/duotone.py`'s `get_cached_hero`/
`duotone_and_cache`) was `brief.topic_id` alone (plus mood palette) —
never the angle, `visual_subject`, or fingerprint. Any two posts on the
same topic+mood, however different their angles, silently returned the
exact same cached hero image, skipping image generation entirely on every
call after the first for that topic+mood pair (this is what Report B's
"identical hero image on regenerate" traced to, separately from the text
drift).

**Fix (`routes/generate.py`):** added `_hero_cache_keyword(brief,
*, variant=None)` — `topic_id` (namespacing) plus a 16-char sha256 prefix
of `brief.hero_image_prompt`. `hero_image_prompt` is already a real
`ContentBrief` field (unlike `visual_subject`, which is folded into it at
brief-build time and then discarded, per logbook #4) and is exactly the
angle-specific visual content the cache should key on, so this needed no
new field or frontend/`api-types.ts` change. `_generate_hero` now uses
this keyword; `reshuffle_image_route`'s existing `:v{variant}` suffix
mechanism is layered on top of the same content-aware base instead of
appending directly to `topic_id` — which, as a side effect, also fixes
the same collision bug for reshuffle (two different angles on one
topic+mood reshuffling to the same variant number previously collided
too; they no longer do), while leaving reshuffle's "fresh variant number
= new image, repeat a variant number = free cache hit" behavior unchanged.

**Not a blueprint deviation** — blueprint.md never specified the cache
key's exact composition, only that hero images should be "cached by
keyword + mood palette."

### Verified

- **111/111 backend tests passing**, no regressions.
- **Deterministic check:** `_hero_cache_keyword()` — two different
  `visual_subject`s on the same topic+mood now produce different
  keywords; the identical brief still produces the identical keyword
  (cache-sharing preserved for genuinely repeated work); reshuffle variant
  numbers no longer collide across different angles.
- **Live, real-API check (main repro):** re-ran the exact
  wellness-motivational/`myth_vs_fact` scenario from the investigation
  report end to end (draft → critique → refine). Zero workplace-term hits
  in either the draft or the refined post; content stayed grounded in
  fatigue/rest/body throughout ("crashing at 9pm on a Tuesday," "your
  body slowing down is a protective system," "what did I say yes to today
  that I actually wanted to say no to"). Before the fix, the same scenario
  produced "in front of your team," "career suicide," "crying in a
  bathroom stall at 4pm" starting from the very first `draft_post` call.
- **Live, real-API check (5 more direct-register trials):** `educational`
  (Women's Health/hormonal-cycle), `common_mistakes`
  (Relationships/boundaries), `stat_research` (Society/pay-scale),
  `framework` (Mindset/rest), `checklist` (Wellness/sleep) — 0 of 5 drifted
  to an invented workplace/meeting scenario. One angle (mindset-rest)
  legitimately named "workplace culture" as one of three real-world
  sources of a belief the post was specifically about tracing the origin
  of — correct, on-topic content, not the old failure mode of a full-post
  pivot to an office scene.
- **Live, real-API check (poetic register, sanity only):** `story`
  (mindset-attachment-styles) and `question_reflection`
  (relationships-quirky-fun) both ran cleanly with zero workplace-term
  hits, as expected since their voice samples were never touched. One
  `story` trial hit an unrelated, pre-existing shape-mismatch error (model
  returned 5 slide objects for a 4-slide role list) — not caused by this
  fix; same failure class as the still-open #29, noted here rather than
  investigated further since it's out of this entry's scope.
- **Live, real-API check (Rosa Parks/NAACP regression, logbook #14's
  baseline):** re-ran the exact citation-grounded myth-vs-fact scenario.
  Draft, critique, and refined output all stayed fully grounded in the
  Rosa Parks/NAACP story across all 4 slides. One residual, much smaller
  trace did surface: `refine_post`'s caption added a "you've felt this
  too" bridge (in response to critique correctly flagging the draft as
  third-person with no direct reader address) that included "the meeting
  you nailed gets called 'lucky'" as one of two brief relatable
  comparisons. This is a single incidental word in one bridging sentence,
  not a full-post pivot away from the accepted angle — the Rosa
  Parks/NAACP content itself was untouched — and is a categorically
  smaller failure than logbook #14's original "refine_post abandoned the
  accepted angle for an unrelated scenario." Noted transparently rather
  than omitted: the fix eliminates the systemic full-post drift; it
  doesn't guarantee the word "meeting" can never appear in any generated
  text again, since it's ordinary English vocabulary the model can still
  reach for on its own when asked for reader-relatable examples.
- **Live, real-API check (hero cache):** two different `visual_subject`s
  on the same topic+mood produced two distinct cache files and distinct
  image bytes (previously would have collided into one); re-requesting
  the identical brief was confirmed to still be a free cache hit (no new
  API call, no new file); the reshuffle `:v{variant}` path was confirmed
  to still generate a fresh image per new variant number and cache-hit on
  a repeated variant number.

**Not committed or pushed** — held for review per explicit instruction,
given this touches core brand-voice content and a caching mechanism used
on every generation. The production Supabase `brand_kit` row also still
needs a separate, explicit decision (see Fix 1's caveat above) before
this fix is live, independent of the git push decision.

**Correction (this session):** both decisions above were in fact made — commit `7f3474c` is on `origin/main`, and the production Supabase `brand_kit.voice_samples_direct` row was independently confirmed live-matching the revised samples via a direct read-only Supabase REST query (`updated_at: 2026-07-16T01:05:57Z`). The lines above were accurate when written but were never updated after both decisions landed.

---

## 31. OPEN — the blueprint's compounding-voice mechanism has never actually persisted anything in production

**Status: open, carried forward for a dedicated session — same treatment
as #29's carried-over item. Discovered as a side effect of #30's
production upsert decision, not separately fixed here.**

**What was found:** blueprint.md Section 4 describes `voice_samples` as
compounding over time — *"every export and every edit she makes appends
to the matching register's list... weeks in, generation pattern-matches
to things she's actually approved, not to a static description of her
voice. This is the single highest-leverage input against generic
output."* Read the live production `brand_kit` row directly (not the
local Python constant, not a cached value) ahead of #30's upsert: both
`voice_samples.poetic` and `voice_samples.direct` were still exactly 5
entries each, byte-for-byte identical to the original seed constant from
Phase 6 (logbook #9). The app has been live and in real use since then —
if the compounding mechanism were actually persisting, at least one of
these arrays should have grown.

**Root cause:** `engine/memory.py`'s `append_voice_sample()` exists,
computes the correct thing (looks up the register via
`APPROACH_REGISTER`, appends the approved copy to the right list), and
returns a new `BrandKit` — but its own docstring says outright
*"callers are responsible for persisting it (no `brand_kit` store exists
yet)."* Grepping the app for callers of `append_voice_sample` turns up
none in any route — nothing in the editor/export flow calls it, and
nothing writes the result back to Supabase via `upsert_brand_kit()` or
otherwise. The function is a correct, unused building block; the
persistence wiring described in the blueprint was never actually built,
despite `brand_kit` itself being fully migrated to Supabase in #9.

**Impact:** every post generated so far — and every post going forward
until this is fixed — draws on a `voice_samples` list frozen at its
original 5+5 seed, never learning from what she's actually approved,
edited, or exported. Per the blueprint's own framing, this is "the single
highest-leverage input against generic output," so this gap is worth
prioritizing, not just noting.

**Not fixed here — deliberately**, out of scope for #30's read-only
verification step. Worth a dedicated session: candidates worth checking
first would be where in the export/edit flow the append should actually
trigger (on export confirmation? on a swipe-edit save?), and whether
`append_voice_sample`'s return value should flow through a new
`upsert_brand_kit()` call directly, or through a small `BrandKitStore`
wrapper matching the `MemoryStore`/`PicksStore` pattern already used
elsewhere.

---

## 32. Masthead simplified to `masthead_short` only — explicit request, deviates from blueprint Section 12

**What changed:** every slide's masthead (`frontend/components/slides/Masthead.tsx`,
shared by all 6 templates — the five locked in Phase 1 plus
`CarouselBodyTeaching`, logbook #3) now renders only `masthead_short`
("WGS"). The thin rule/separator and the `{primary_category} NO. {n}`
text that used to follow it are removed entirely, per explicit request to
simplify what she sees on every slide.

**This is a deliberate deviation from blueprint.md Section 12**, which
specifies the masthead as doing two jobs at once: making a lone
screenshot recognizable as hers, and — via the category+number —
"signal[ing] what kind of post it is." This change keeps the first job,
drops the second. Not a bug; logged per the phase-gating/logbook
discipline rule that any deviation from a written design decision gets
called out explicitly, even when directly requested. `docs/blueprint.md`
Section 12 was left as-is (still accurately describes the original
design intent and the backend mechanism, which is unchanged) rather than
rewritten, since the doc's job here is to record what was decided and
why, not to be silently edited to match; this logbook entry is the
record of the deviation.

**Confirmed before changing anything — the masthead number is genuinely
display-only, not wired into anything functional:** grepped the backend
for `next_masthead_number` (`models/memory.py`) — its only two callers
are `engine/brief_builder.py` and `sources/paste_link.py`, both just
building the display string returned to the frontend. Content memory's
non-repetition filter (angle engine) keys on `fingerprint`
(`topic+angle+approach`), never the masthead number. `selector.py`'s
coverage weighting (`_topic_weight`) counts `MemoryRecord`s by
`topic_id`, also never the masthead number. This matches blueprint
Section 11's own framing of the masthead count as "a simple,
deterministic Python query" that exists to compute a displayed string,
not a value anything else reads back. So this change is genuinely
frontend-display-only, as scoped — no backend behavior changes.

**What was deliberately left untouched, per explicit instruction:**
`next_masthead_number()` and `brief_builder.py`'s masthead-string
computation are fully intact and still run on every `/generate` call —
the backend still computes and returns `"WGS — MINDSET NO. 14"` as
before; the frontend's `MastheadInfo` type, `parseMasthead()`, and every
route that threads `category`/`number` through
(`SlideRenderer.tsx`, `/api/render`, `editor/page.tsx`, `export/page.tsx`)
are also unchanged — they still carry the full data, `Masthead.tsx` just
no longer renders two of its three fields. Reversing this later is a
one-file change.

**Verified both the editor-preview and `/api/render` (Satori/`@vercel/og`)
paths actually share this one component**, rather than assuming it from
the file being imported in both places: `SlideRenderer.tsx` (used by the
live editor preview) and `app/api/render/route.tsx` (the real PNG export
route) both import the same six template components
(`CarouselCover`, `CarouselBody`, `CarouselBodyTeaching`,
`CarouselClosing`, `SingleQuote`, `SingleStat`) directly, and each of
those six imports `Masthead.tsx` internally — confirmed via grep, not
inferred from the docstrings alone. One edit to `Masthead.tsx` reaches
both paths with no route-specific override anywhere in between.

**Verified rendering, real output, not just code review:** no browser-
automation tool was available in this session, so verification ran
through the actual `/api/render` (Satori) route directly — the same
route both `/preview` and the live editor call, confirmed above to share
the identical component tree. Rendered all 6 templates × all 3 moods (18
real PNGs) via real POST requests to a locally running `next dev` server,
deliberately passing a *non-empty* `category`/`number` in the request
payload ("MINDSET" / "14") to prove they're truly not rendered even when
present in the data, not just absent because the test data was blank.
Visually inspected a representative sample across template types
(cover, body-teaching, closing — including its masthead-color-override-
on-dark-background case, and single-stat) and moods: every slide shows
only "WGS," no rule, no dangling category/number text, and no leftover
spacing artifact where the removed elements used to sit (the masthead
row is a plain flex row with intrinsic sizing, not a fixed-width or
justify-between container, so removing two children just makes the row
narrower — no other template's layout depends on the masthead's
rendered width). `npx tsc --noEmit` — clean, no type errors from the
unused-but-still-passed `category`/`number` fields on `MastheadInfo`.

**Not committed or pushed** — held for review per explicit instruction.

**Correction (this session):** this was in fact committed (`65166fa`), pushed, and is confirmed live in production — see verification below. The line above was accurate when written but was never updated after approval.

**Deployed verification (this session):** a real `POST /api/render` call against `https://wgs-studio.vercel.app`, deliberately sending non-empty `category`/`number` (`"MINDSET"` / `"14"`) in the payload — the same technique this entry's own verification used — confirmed the live rendered slide shows only `"WGS"`, no rule, no category/number text, even though that data was explicitly present in the request.

---

## 33. Investigation-only follow-up to #31: no export event exists at all, a second dormant bug found (masthead counter always "01"), and the cache-invalidation premise in #31's own framing was wrong

**Status: read-only investigation, explicitly requested as such — no code touched, nothing
committed.** Scoped to answer five specific questions about #31 (the voice-compounding
mechanism never persisting) before any implementation is attempted. Everything below is
traced against the actual repo and two live, read-only checks (a Supabase `select` query
against `brand_kit`/`memory`, and the Anthropic `count_tokens` endpoint) — no `/generate`
call, no write of any kind.

**1. Where export confirmation lives — it doesn't; there is no export-confirmation event
at all.** Every `MemoryRecord` is created with `status="draft"` hardcoded
(`routes/generate.py:188-201`); grepping the whole backend for `status="exported"` outside
test files returns nothing. There is no `routes/export.py` or `routes/brand.py` — only
`topics.py`, `picks.py`, `sources.py`, `generate.py` exist. `frontend/app/export/page.tsx`'s
`handleDone()` only clears `sessionStorage` and navigates home — zero network calls. The
editor's inline text edits (`updateSlide()`) only mutate local React state; the only two
backend calls from the editor are regenerate-slide and reshuffle-image, both generation
calls, not saves. **#31's own framing — "which event should trigger the append, export
confirmation or a swipe-edit save?" — assumes two events that don't exist as
backend-observable events today.** Either has to be built from scratch.

**A second, previously unflagged bug surfaced by the same trace:** since `status` never
becomes `"exported"`, `next_masthead_number()` (`models/memory.py:24`,
`1 + sum(... and r.status == "exported")`) has been computing `1 + 0` for every category on
every call since Phase 6. **Every post's masthead number has always been "01."** This is
independent of #32 (which only stopped *displaying* the number) — the backend value itself
has been wrong the whole time. Not fixed here — logged so it isn't rediscovered as a
mystery later.

**2. Persistence pattern — `MemoryStore`/`PicksStore` are real; `BrandKitStore` is
unnecessary scope.** `MemoryStore` (`engine/memory.py`) is a real dual-backend class
(Supabase when constructed with no path, file-backed for tests). `PicksStore`
(`engine/selector.py`) is real but unconditionally file-backed — no Supabase branch, unlike
`MemoryStore` (noted, not chased further). No `BrandKitStore` class exists anywhere;
`db.upsert_brand_kit(kit)` (`db/supabase.py:54`) already does the full write in one call, so
a wrapper class isn't required to close #31 — only worth adding if file-backed test
hermeticity matching `MemoryStore`'s pattern is wanted.

**3. Live `voice_samples` — still 5+5 (confirms #31's core finding still holds), but the
content has moved since #31 was written.** Queried the live `brand_kit` row directly: both
arrays are still exactly 5 entries, so no compounding has happened. But `direct` no longer
matches the original workplace-themed seed #31 quoted — it now matches the #30 revision,
meaning someone/something already upserted the new value to production, even though #30's
own text describes the production row as "deliberately NOT touched," left as an explicit
open follow-up. Flagged as a discrepancy for whoever owns that decision — not resolved
here. Measured sizes via `count_tokens` (`claude-sonnet-5`): poetic block 427 chars / 147
tokens, direct block 635 chars / 207 tokens.

**4. Token/cost impact of growth — real numbers, and the cache-invalidation question in
#31's own notes turned out to be based on a wrong premise.** The injection point is
`generator.py:264`/`:304` inside `_brief_system_prompt()`; `brief.brand_voice_samples` is
**one resolved register only** — a single `/generate` call injects 5 lines today, not 10.
`providers/llm.py`'s `cache_control` wraps the *entire* system string as one block, and that
string is brief-specific (topic/angle/approach/tone all baked in) — so the cache already
invalidates on **every single post, unconditionally**, regardless of `voice_samples` size or
export cadence. There is no export-frequency-driven invalidation rate to compute, because
nothing is currently shared *across* posts at all; the only real caching that happens is
within one post's 3 sequential calls (draft/critique/refine build byte-identical system
strings, so calls 2-3 read the cache call 1 wrote). Real cost curve at Sonnet 5 pricing
(measured 35.4 tok/line average): growing to 10/20/30/50 lines per register costs an
incremental **$0.0008 / $0.0023 / $0.0039 / $0.0069 per post** — under a cent even at 10x
growth. The real constraint on any cap is prompt quality (diluting/contradicting few-shot
examples), not token spend.

**5. Extraction logic — blocked on a bigger gap: no full post content is persisted
anywhere, ever.** `MemoryRecord.hook` is `slide_text(post.slides[0])[:80]` — first slide
only, truncated to 80 characters. The caption is never stored. The full `GeneratedPost`
exists only in the HTTP response to the frontend and client-side session state after that —
nothing durable server-side. **Any extraction strategy has to run inline during
generation/export, not as a later job reading `memory`**, since `memory` never had the
content to begin with. Illustrated three candidate strategies (first-standout-slide-line,
caption-hook, LLM-picked-best-line) against two real (truncated) production hooks pulled
live — first-standout-line is free (arguably already computed as `hook`, just cut short for
a different purpose); caption-hook needs a new persisted field; LLM-picked-best-line needs
either a new call or piggybacking onto `critique_post`'s existing response, the same trick
already used for mood-tagging in #4.

**Not a blueprint deviation** — pure investigation, no code or config changed. Carries
forward #31's OPEN status with a corrected, more specific problem statement: the export
event needs to be invented (not hooked), a masthead-counter bug needs a separate fix, and
extraction has to be wired into the live generation path rather than read back from
`memory`.

---

## 34. `brand_kit`'s RLS policy was wide open to any authenticated session — root cause of #30/#33's untraceable production discrepancy; tightened, plus a database-level audit trail

**Symptom, traced across several read-only turns before anything was changed:** #30 rewrote `voice_samples.direct` in code but explicitly said the live Supabase `brand_kit` row was "deliberately NOT touched." #33's investigation found the live row already matched the new value anyway, with no caller of `upsert_brand_kit()` anywhere in the app to explain it (`get_brand_kit()`'s self-seed branch only fires when the table is empty, and the table was never empty across this window). A dedicated investigation across the next several turns ruled out every code-level explanation one at a time:

- **Deploy/commit state** — confirmed via `git log`, `railway status --json` (exact `commitHash` match), and `vercel inspect`/alias timing that #30 (`7f3474c`) and #32 (`65166fa`) were both committed, pushed, and deployed correctly — not an artifact of an un-pushed or partially-deployed change.
- **The seeding mechanism itself** — read `get_brand_kit()`/`fetch_brand_kit()`/`upsert_brand_kit()` directly: the "should I seed" check is a real row-existence check (`if not res.data: return None`), not a fragile key/None check; `get_brand_kit()` runs per-request (no caching), but harmlessly, since the check only ever fires the seed branch on a genuinely empty table; `upsert_brand_kit()` has exactly one call site in the entire repo (grepped, no scripts/tools directory exists); neither file's logic has changed since it was first written in `7d898fd` (confirmed via `git log --follow`); and Railway showed **zero backend restarts** since #30 deployed (one deployment, one instance, one `Application startup complete` line in the logs) — so there was no restart-triggered reseed window for this to have happened in even if the check had been fragile, which it wasn't.
- **Frontend as a bypass path** — grepped all of `frontend/` for `.from("brand_kit")` / `.from("memory")` / `.from("image_cache")`: zero matches across all three tables. The frontend's only Supabase client (anon-keyed) is used exclusively for `.auth.*` calls (session, sign-in, sign-out) in 3 files — it never touches any table.
- **RLS policy, queried live** (no `psql`/pg driver was available locally, so this used an ephemeral `uv run --with psycopg2-binary` against `SUPABASE_DB_URL` — nothing added to the project's tracked dependencies): `brand_kit` had RLS enabled with exactly one policy, `authenticated_full_access` — `FOR ALL TO authenticated USING (true) WITH CHECK (true)`. **Fully open read and write access to any session holding a valid `authenticated` JWT** — not select-only, and matching `schema.sql` exactly (no drift between repo and deployed state). This is the actual explanation: nothing in application code wrote the new value: the RLS design itself always permitted a direct out-of-band write (Supabase dashboard Table Editor, or a manual REST call with a valid authenticated session) to freely rewrite `brand_kit`, completely independent of any app code path.
- **Server-side logs** — checked whether Supabase's own Postgres/API/Auth logs could show *who* made the change. No access path exists from this environment (no Management API personal access token, no `supabase` CLI installed) to query them, and the project is documented as Supabase Free tier, whose log retention is short enough that the July 13-15 window has very likely already rolled off even with access. Reported plainly as "cannot reach, not "no evidence found"" — this was never confirmed one way or the other, and won't be.

**Root cause:** `brand_kit` (and, by the same design pattern, `memory` and `image_cache`) granted full CRUD to any `authenticated` session with no row-level restriction, for a single-creator app with exactly one real auth user. Nothing needed exploiting — the RLS policy itself was the gap. The *who/when* of the specific July 2026 change remains genuinely unknown (logs unreachable) and is not going to be resolved further; the fix closes the mechanism regardless of attribution.

**Fix, applied directly against production Supabase (`SUPABASE_DB_URL`, service-equivalent `postgres` role) after a design review and explicit go-ahead — SQL shown and approved before it ran:**

- `revoke select, insert, update, delete on brand_kit, memory, image_cache from authenticated;` and dropped all three `authenticated_full_access` policies. No replacement policies were added — RLS stays enabled with zero policies for either `anon` or `authenticated`, so both are now locked out of direct reads and writes on all three tables at the object-permission layer (confirmed live, see Verified). `anon` was already effectively locked out before this (no matching policy existed for it); this change doesn't touch `anon`'s config, only makes the lockout explicit at the grant level too, matching how it already behaved.
- Added a new `audit_log` table (`table_name`, `operation`, `row_id`, `old_value`/`new_value` as `jsonb`, `changed_at`, `db_user` = `current_user`, `auth_role` = `auth.role()`, `auth_uid` = `auth.uid()`) plus a `security definer` trigger function (`audit_row_change()`) and `AFTER INSERT OR UPDATE OR DELETE` triggers on `brand_kit` and `memory` (not `image_cache` — deliberately scoped this way, matching the design that was reviewed and approved; `image_cache` got the RLS tightening but not an audit trigger). The trigger function's `security definer` is what lets it record a write successfully even from a role that otherwise has no privileges on `audit_log` itself.
- **Found during pre-commit review, fixed in the same arc before anything landed:** `audit_log` was initially described above as "locked down the same way" as the other three tables, but it wasn't — it only had `alter table audit_log enable row level security;` with zero policies, and never got an explicit `revoke`. Re-testing it with the same throwaway-user method (see Verified #1) showed `SELECT` as `authenticated` returned **`200` with an empty array**, not a `403` — Supabase's default schema-level privileges still granted `authenticated`/`anon` base `SELECT` on this brand-new `public`-schema table, so the query was *permitted* at the grant layer and only then filtered to zero rows by RLS (no policy to satisfy). No data was ever actually exposed (empty result either way), but it wasn't the same denial mechanism as the other three tables, and it was inconsistent with them. Fixed with `revoke select, insert, update, delete on audit_log from authenticated, anon;` — matching the explicit-revoke pattern already used on `brand_kit`/`memory`/`image_cache`, rather than relying on RLS-with-zero-policies alone. `schema.sql` updated to include this line and an explanatory comment.
- Added a `logger.warning(...)` line in `get_brand_kit()`'s seed-on-empty branch (`taxonomy/wgs_brand_kit.py`) so a reseed event is visible immediately in Railway's live logs, not only queryable later via `audit_log`. This is the first `logging` usage anywhere in this backend (grepped — none existed before); uses a plain stdlib `logger = logging.getLogger(__name__)`, no new configuration needed since uvicorn's existing setup already surfaces it.
- `backend/app/db/schema.sql` updated to match exactly what was applied live, so the repo stays the source of truth.

**Verified, in this order, against live production:**
1. **`authenticated` is genuinely locked out — on all four tables, not just three.** Created a throwaway Supabase Auth test user via the admin API (service_role), signed in as it to get a real `authenticated` JWT (same pattern as #8's own RLS verification), and attempted `SELECT` on `brand_kit`/`memory`/`image_cache` plus `INSERT`/`UPDATE` on `brand_kit`: all 5 returned `403` / `permission denied for table ...` (Postgres code `42501`). `audit_log` initially did not (see the pre-commit-review fix above) — re-ran the identical test against `audit_log` alone after applying its own `revoke`, and it now returns the same `403 permission denied for table audit_log` on `SELECT`, matching the other three exactly; `INSERT` on `audit_log` was already correctly rejected before this fix, by RLS's `WITH CHECK` rather than the grant layer. Test users deleted immediately after each run.
2. **Backend unaffected** — `GET /topics` on the live Railway URL: `200`. A real `POST /generate` (single_image/stat, topic `mindset-self-doubt`) against production: `200` in 27.6s, `validation_errors: []`, correct single-slide output — service_role continues to bypass RLS exactly as designed, confirming the tightening didn't touch the app's own access path.
3. **Audit trail captures real writes correctly** — the `/generate` call above wrote a real `memory` row; `audit_log` captured it (`operation: INSERT`, `auth_role: service_role`, correct `row_id`). Separately, ran one harmless, reversible-in-spirit test write directly against `brand_kit` (`update brand_kit set updated_at = now()` — touches no actual brand content) to exercise the `UPDATE` path without needing to risk the seed-on-empty branch against a table that already holds real data: `audit_log` captured `old_value`/`new_value` correctly (only `updated_at` differed; `voice_samples_direct` confirmed byte-identical old vs. new), with `db_user: postgres`, `auth_role: NULL` (correctly `NULL` since this was a direct Postgres connection, not a PostgREST-proxied request with a JWT — `auth.role()`/`auth.uid()` only populate under a real request context, exactly as designed).
4. **Full test suite: 111/111 passing**, no regressions — re-run again after the `audit_log` grant fix, still 111/111.

**Review sequence before landing on `main`:** the SQL for both the original three-table tightening and the `audit_log` follow-up fix was shown and explicitly approved before running against production, in that order; the pre-commit read of the diff is what caught `audit_log`'s inconsistent lockout in the first place, folded into this same entry rather than opened as a new numbered issue, since nothing had been committed yet at that point.

**Not a blueprint deviation — infrastructure hardening.** `blueprint.md`/`implementation-guide.md` never specified RLS policy shape beyond "the backend uses service_role" (Section 15/`implementation-guide.md` Section 9); the original `authenticated_full_access` policy was itself a post-Phase-6 addition (#8), not a locked blueprint value, so tightening it doesn't reverse or contradict anything the design docs committed to.

---

## 35. Export-confirmation event built (#31/#33) — real content persistence, voice-compounding, masthead counter fixed for free; plus a live-discovered `brand_kit` duplicate-row bug, found, fixed, and hardened during this feature's own verification

**What this closes out.** #31/#33 found the blueprint's "every export appends to voice_samples" mechanism (Section 4) had never actually fired in production: no export-confirmation event existed at all, `MemoryRecord.status` was hardcoded `"draft"` forever, and — as a direct consequence, since the masthead counter only counts `status == "exported"` records — every masthead had shown `NO. 01` since Phase 6. This entry builds the missing event and, in the same pass, fixes a real, previously-undiscovered bug the new code's own live verification surfaced.

**Built:**
- **Schema:** `memory` gained `caption text not null default ''`, `slides jsonb not null default '[]'`, `exported_at timestamptz` (migration approved and applied directly against production before any code was written, same checkpoint pattern as #34's RLS work). `slides` stores the same discriminated-union shape as `GeneratedPost.slides` (`models/post.py`) — not opaque JSON.
- **Backend models:** `MemoryRecord` gained `caption`/`slides`/`exported_at`. `GenerateResponse` gained `memory_id: str`, populated from the `MemoryRecord.id` that was already being generated (`uuid.uuid4()`) and persisted on every `/generate` call but previously discarded rather than returned to the client. `db/supabase.py` gained `fetch_memory_by_id()`/`update_memory()`; `engine/memory.py`'s `MemoryStore` gained matching `get()`/`update()` methods (dual file-backed/Supabase-backed, same pattern as `load()`/`append()`).
- **`routes/export.py`, new — `POST /export/confirm`:** takes `memory_id`, `caption`, `slides`, `train_voice: bool`. Idempotency guard: a record already `status == "exported"` short-circuits to a no-op (`already_exported: true`), never re-saves content, never re-runs extraction, never double-appends a voice sample. Otherwise sets `status = "exported"`, `exported_at = now()`, saves the real caption/slides, and — if `train_voice` — resolves the register from the record's own stored `approach` via `APPROACH_REGISTER` (the client never sends it), runs one cheap-tier call reading the real final content to pick the single best line (`_extract_best_line`, same defensive fallback pattern as `angle_engine._parse_angle_response` — never raises, falls back to the first slide's text), and calls `append_voice_sample()` + `upsert_brand_kit()`. `append_voice_sample()` (`engine/memory.py`) gained a `VOICE_SAMPLE_CAP = 10` FIFO cap: at 10 entries, the oldest is dropped before the new one is appended, so the compounding mechanism can't grow the few-shot block unbounded.
- **Malformed-slides protection, per explicit instruction:** `ExportConfirmRequest.slides` is typed as the real `list[Slide]` discriminated union, not a raw dict/`list[Any]` — FastAPI validates every slide through `CoverSlide`/`BodySlide`/`BodyTeachingSlide`/`ClosingSlide`/`QuoteSlide`/`StatSlide` (via `template_id`) at the request boundary, before the handler ever runs. A malformed or unexpected `template_id` gets a `422` and never reaches `MemoryStore.update()`, let alone Postgres.
- **Frontend:** `export/page.tsx` gained a `savedImages` state (same tracking rigor as the existing `copied` state, minus its 2s auto-revert) and a "Use this post to improve future writing" toggle — defaults off, auto-flips true the first time `handleDownloadAll()` fires, never auto-reverts after that (checked via `!savedImages` at the top of the handler, so a second "Save images" tap won't re-force it back on if she manually turned it off). `handleDone` now calls the new `confirmExport()` endpoint with `memory_id`/`caption`/`slides` (from the same `data` object already confirmed, in an earlier read-only investigation this session, to hold every editor edit) and the toggle's state, blocking navigation and showing an error on failure rather than silently losing the confirmation.
- **Tests (`test_export_route.py`, 9 new):** idempotency (a second confirm is a true no-op — an empty LLM response queue on the second call means a real re-trigger would raise `IndexError`, not silently pass), register resolution from the record's stored `approach` (not client-supplied), FIFO cap eviction at exactly 10 (oldest dropped, newest at the end) and just-below-cap (no eviction), malformed/missing `template_id` both `422`, unknown `memory_id` `404`, and the masthead counter genuinely incrementing after a real `status="exported"` transition through the route (not just the pre-existing unit test of `next_masthead_number()` in isolation). Full suite: 111 existing + 9 new = **120/120 passing**.

**Live-discovered bug, found during this feature's own verification, not code review:** running the real `/generate` → `/export/confirm(train_voice=true)` sequence against production (local server, real Supabase + Anthropic — the same "local dev server against production-configured `.env`" pattern #24 used) reported `voice_sample_appended: true`, but a direct query showed `brand_kit.voice_samples.direct` **unchanged**. Investigation found `brand_kit` now had **two rows**: the original (`b32b871d-...`, untouched, still 5 entries) and a brand-new one (`e6172e12-...`, 6 entries — the correct compounding logic had run, but the write landed on a duplicate row instead of updating the existing one). `audit_log` itself proved the mechanism directly: entry recorded `operation: INSERT` (not `UPDATE`) on `brand_kit`, `row_id` matching the new duplicate.

**Root cause:** `db.upsert_brand_kit()` — original code from #9, not anything written for this feature — calls `.table("brand_kit").upsert({...})` with no `id` in the payload and no `on_conflict` target. With nothing to conflict on, Supabase/PostgREST silently inserts a new row instead of updating. This bug has existed since #9 but never manifested: its only caller before this feature was `get_brand_kit()`'s self-seed branch, which by definition only ever runs when the table is *empty* — an insert was accidentally correct there. `routes/export.py`'s voice-compounding write is the first caller in the project's history that ever needed `upsert_brand_kit()` to update an *existing* row, and that's exactly where the latent bug surfaced.

**Fix, applied directly against production after explicit approval, in this order:**
1. Deleted the duplicate row (`e6172e12-...`). Confirmed afterward: exactly one row, `b32b871d-...`, `voice_samples_direct` back to its original untouched 5 entries.
2. Rewrote `upsert_brand_kit()` to look up the existing row's `id` fresh and `UPDATE` by it; only `INSERT` when the table is genuinely empty. `BrandKit` still carries no `id` field — the lookup happens at write time inside `upsert_brand_kit()` itself, nothing upstream needed to change.
3. Added a structural safeguard, not just a "the code should behave now" hope: `create unique index brand_kit_singleton_idx on brand_kit ((true));` — a unique expression index on a constant, so a second row is rejected by Postgres itself regardless of what any future code does. Applied only after step 1's cleanup (Postgres refuses to create a unique index over existing duplicates). Verified it actually works with a real second-insert attempt against production, which failed exactly as intended: `duplicate key value violates unique constraint "brand_kit_singleton_idx"`.

**Verified live, for real — including a real accidental confirmation of the safeguard along the way:** a stale local server (old process still bound to the port after an incomplete restart) tried the export-confirm flow again on the *unfixed* code — the new unique index correctly rejected its blind insert attempt with a clean `500`/constraint violation instead of silently creating a second duplicate. Properly killed and restarted against the actually-fixed code, then re-ran end-to-end: `voice_sample_appended: true`, `brand_kit` still exactly one row (same `id`, `b32b871d-...`), `voice_samples_direct` genuinely grew to 6 entries via a real `UPDATE` (confirmed via the row's own `id` staying constant, not a new one). Reverted the register back to its original 5 immediately after confirming — this test line doesn't belong in production any more than the first, failed attempt's did.

**Masthead counter confirmed fixed, live, not just via the unit test:** after the one real Mindset export made during this verification, a subsequent plain `/generate` call (draft only) for the same category reported `WGS — MINDSET NO. 02` — the first time in this project's history the masthead has ever shown anything but `NO. 01` for a real live call, confirmed directly, not inferred.

**Cleanup — every test artifact this verification created was removed, not left behind:** three `memory` records ended up genuinely `status = "exported"` during this process (one Mindset, two Career — the second Career export happened because a stale-server retry had already committed the record's `status`/content mutation before failing later in the same request on the old, unfixed `upsert_brand_kit()` call — see the non-atomicity note below). All three were deleted once every verification step that needed them had run; production has zero real exports again. Plain `draft`-status records created along the way were left in place, matching the already-established precedent that draft records are harmless/inert (they don't count toward the masthead, and don't feed the non-repetition filter any differently than any other draft).

**Follow-up, same session, before anything was committed — the non-atomicity above was fixed, not left open.** Originally logged here as "observed, not fixed" — `store.update()` (marking `status = "exported"`, saving content) committed *before* the `train_voice` block's `db.upsert_brand_kit()` call, so a training failure left a record permanently `exported` with no way to retry just the training half, since the single shared idempotency guard (`if record.status == "exported": no-op`) treated any retry as already-done. Flagged immediately, then fixed in the same pass rather than carried forward as a new open item:

- **Schema/model:** `memory` gained `voice_trained_at timestamptz` (nullable, no default — applied directly against production, same checkpoint pattern as everything else in this entry); `MemoryRecord` gained the matching field. `NULL` means training hasn't successfully completed, the same meaningful-null pattern `exported_at` already used.
- **`routes/export.py` restructured** so content-persistence and voice-training are two genuinely independent idempotency checks instead of one shared guard: `status`/`exported_at` still govern whether content gets (re-)saved; `voice_trained_at` alone now governs training. If `status` isn't yet `"exported"`, content is persisted as before. Training then evaluates independently, off the record's real saved content either way: `train_voice=false` → untouched; `voice_trained_at` already set → skipped (no double-append); `voice_trained_at` still `None` → a real attempt runs (extraction → `append_voice_sample()` → `upsert_brand_kit()`), and `voice_trained_at` is set *only* after every step genuinely succeeds. A failure is caught, logged (`logger.exception`, the first use of Python's `logging` module in `routes/export.py`), and left with `voice_trained_at` still `None` — explicitly retryable on a later call with the same `memory_id`, which was structurally impossible before this fix.
- **Response shape** now distinguishes the training outcome independently of content-persistence: `voice_training_status: "appended" | "already_trained" | "not_requested" | "failed"`, replacing the old single `voice_sample_appended: bool` (which conflated "training ran and succeeded" with "training was skipped because content was already exported" — exactly the coupling this fix removes). `already_exported: bool` now describes the content-persist half only. Frontend `ExportConfirmResponse`/`VoiceTrainingStatus` types updated to match — `export/page.tsx` never inspected the old field, so no other frontend logic needed to change.
- **Tests (2 new, `test_export_route.py`, now 11 total for this route):** a mocked training failure (`_RaisingLLM`, simulating a real call failure — rate limit, network — distinct from `_extract_best_line`'s own internal parse-fallback, which still never raises) leaves `status="exported"` but `voice_trained_at=None` and `voice_training_status: "failed"`; a subsequent retry call with the same `memory_id` and `train_voice=true` again then genuinely succeeds and sets `voice_trained_at` — proving the retry path directly, with an empty mocked-LLM response queue on the *first* attempt's failure path guaranteeing no accidental extra call. A separate test confirms a repeat call after a *real* success returns `already_trained` and doesn't double-append (`upsert_brand_kit` called exactly once, `voice_trained_at` unchanged from the first call's timestamp). Full suite: **122/122 passing** (120 + 2).
- **Live check, real data, not just mocks:** real `/generate` → `/export/confirm(train_voice=true)` (genuine success, `voice_training_status: "appended"`) → an immediate second real call with the same `memory_id` and `train_voice=true` again (`already_trained`, `0.2s` vs. the first call's `3.8s` — confirming no LLM call was even attempted the second time, not just that the response looked right). Verified directly against Supabase: `brand_kit` still exactly one row, `voice_samples_direct` grew by exactly one entry, not two. Reverted the register to its original 5 and deleted the one test-exported `memory` record immediately after — production held zero real exports and the original brand-voice content throughout everything except the few seconds between the live check and this cleanup.

**Small follow-up, same session, before commit — the failure is now visible to her too, not just server-side logs:** `export/page.tsx`'s `handleDone` reads the existing `voice_training_status` field it already gets back from `/export/confirm`; when `train_voice` was true and it comes back `"failed"`, a brief non-blocking message ("Exported! (Voice training didn't complete this time — no action needed.)") shows for 2.5s before navigating home — the export itself already succeeded, so nothing blocks getting back to the home screen either way. No retry button, nothing persisted client-side; one new piece of transient UI state (`doneNotice`). If `train_voice` was false, or training succeeded/was already done, behavior is unchanged — navigates home immediately.

**Verified overall:** full backend suite **122/122 passing**. `pnpm exec tsc --noEmit` clean throughout, including after the response-shape change and this final UI addition.

**Amended (this session, doc-only pass): partial blueprint deviation, not a clean "not a deviation."** The export-confirmation event, real content persistence, and voice-compounding cap are new functionality implementing what blueprint.md Section 4 and Section 11 already described but was never wired up (#31's own framing) — that much genuinely isn't a departure from anything locked. But the *trigger* is a real, deliberate deviation, named plainly here the same way #25 and #32 named their own: blueprint Section 4 describes automatic capture — "every export and every edit she makes appends to the matching register's list" — with no toggle anywhere in it. What actually shipped is an explicit, off-by-default `train_voice` toggle ("Use this post to improve future writing"), which auto-flips true the first time she taps Save Images but stays switchable off right up until she confirms. This wasn't an oversight; it was chosen deliberately in this session's design discussion, specifically because `voice_samples` directly shapes future generation tone, and automatic capture on every export/edit would feed that pool unreviewed or synthetic content too — a throwaway export made only to check rendering, an unfinished draft — with no way to keep it out after the fact once it's in the register. An explicit, defaults-toward-capture toggle keeps the compounding mechanism's underlying intent (real, approved content training future generation) while adding a genuine off-switch that blueprint.md never specified. blueprint.md Sections 4 and 11 have been updated (this session) to describe the toggle as actually built, rather than continue describing automatic capture that was never true in production. The `upsert_brand_kit()` fix, `brand_kit_singleton_idx` safeguard, and the training-retry decoupling remain bug fixes and correctness hardening, the same classification as #34's RLS work, not a design decision.

---

## 36. CLOSED, not fixed, not carried forward — #13's "hero-image cache rarely hit" is no longer a real gap

**Status: closed.** Not a bug fix, not deferred work — a fresh investigation found the premise #13 was built on no longer holds, so there's nothing left to fix.

**What #13 originally flagged:** the hero-image cache (`providers/duotone.py`, keyed at the time by `topic_id` + mood palette) was "rarely hit in practice because `angle_engine.py` resamples `mood` randomly on every call, changing the cache key almost every time" — logged as a missed cost/efficiency opportunity, not an active bug.

**What's changed since, for an unrelated reason:** #30 rebuilt the cache-key construction (`_hero_cache_keyword()`, `routes/generate.py`) to fix a real content-collision bug — two different angles on the same topic+mood were silently sharing one cached image. The fix keyed on `topic_id` + a hash of the full `hero_image_prompt` instead of `topic_id` + mood alone. That change was scoped to the collision bug, not to #13's cost question — but it happens to touch the same mechanism, so this session investigated whether it also changed #13's answer.

**Investigation (this session, read-only, no code changes):** traced the full path from an accepted angle to the final `hero_image_prompt` sent to GPT Image 2 — `angle_engine.generate_angle()`'s bundled cheap-tier call (which writes `visual_subject` in the same response as the angle/mood/reason, per #4), through `brief_builder._hero_image_prompt(visual_subject, mood)`, to `_hero_cache_keyword()`'s `topic_id:sha256(hero_image_prompt)[:16]`. Confirmed `visual_subject` is a fresh LLM output on *every single call* — never templated, never deterministic — and tested how much it actually varies:

- **Same cell, forced identical 5 times in a row** (byte-identical `topic.name`/`sub_concept`/`approach`/`entry_point`/`knowledge_hints` — the exact same system+prompt text sent to the model every time, via a fixed `random.Random` seed forcing `sample_cell()` to pick the same cell each call): **5/5 distinct `visual_subject` outputs**, 5/5 distinct `hero_image_prompt` hashes. No `temperature` override is passed to the Anthropic call, so this is genuine default-temperature sampling variance.
- **Natural, unforced usage** (6 real calls, no forcing): by chance, two calls (#2/#3) landed on the exact same real cell anyway — still two completely different `visual_subject` values, two different hashes. 6/6 distinct hashes overall.

**Conclusion:** the cache, as it stands post-#30, behaves essentially as "generate fresh every time" — not because anything is broken, but because `hero_image_prompt` is genuinely almost-never identical across two real generations, cell-repeats included. The one case it's actually designed for and does hit reliably is `reshuffle-image`'s `variant` mechanism, which deliberately re-requests the *same* keyword to guarantee a cache hit (`:v{variant}` in `_hero_cache_keyword()`) — that's the correct, wanted behavior, not a gap.

**Why this closes rather than reopens as a new task:** pursuing more cache reuse here would mean either templating/constraining `visual_subject` (directly fighting the prompt's own explicit instruction to be "recognizably specific to this angle, not swappable with any other post's") or hashing on something coarser than the real visual content (reintroducing exactly the collision bug #30 fixed). Both trade away real product value (per-post visual specificity, blueprint Section 9's stated goal) for a cache-hit rate that was never actually achievable given how `visual_subject` is generated. Nothing to build; #13 is closed.

**Separate, deliberately parked note — not part of #13:** the same investigation confirmed `Topic.primary_category`/`categories` never enters the image-generation pipeline anywhere between angle-sampling and the final `hero_image_prompt` — category is used only for the masthead label (`next_masthead_number`) and browse-screen filtering (#25). Whether hero imagery *should* be category-aware is a real, separate product question, not raised or answered here — parked for whenever it's actually asked.

**Not a blueprint deviation** — closing an item that turned out not to need work, not a design decision.

---

## 37. Fixed #29's real root cause — `critique_post` was flagging a fixed-slide-count brief's single slide as a defect, and `refine_post` complied by expanding it

**Root cause, established with live evidence before any fix was attempted** (previous session's read-only investigation): `critique_post()` asks the model to separately check the draft against `_APPROACH_DEFINITIONS[approach]` — definitions like `question_reflection`'s *"the post's content oriented around exploring it"* or `story`'s *"grounds the post in one concrete, relatable scenario"*, written with an implicit assumption of multi-slide room. Nothing told critique that slide count/shape is a fixed, non-negotiable brief constraint (`slide_roles_for`, decided in Python, blueprint decision 3) — so for any approach that structurally "wants" more room than the format actually gives (`single_image`'s fixed 1 slide, most visibly, but not exclusive to it), critique reliably produced a genuine-sounding "this needs more slides/structure" complaint. `refine_post` then complied, expanding the slide count to satisfy a complaint that was never valid. Real captured evidence included the model writing the correct single-slide answer first, then explicitly overriding itself mid-generation ("Wait — I need to actually give you the full multi-slide post, not just one slide. Let me build it properly.") before emitting a second, 5-slide JSON object — direct proof the critique's framing was actively pulling the model away from the brief's actual constraint, not a random JSON-formatting fluke. This corrects #29's own carried-forward hypothesis, which suspected `refine_post`'s prompt didn't reinforce the constraint as strongly as `draft_post`'s — both use the identical system prompt; the defect was one step upstream, in what critique told refine to do.

**Fix, two layers, both scoped to the source finding — not a broad prompt rewrite:**
- `critique_post()` (`generator.py`) gained a new `shape_instruction`, generated from the same `roles = slide_roles_for(brief)` already computed for both formats (not single_image-specific): states the exact fixed slide count and role list, explicitly says it is NOT something to critique regardless of format, and explicitly rules out "needs more/fewer slides or a different structure" as a valid complaint — while explicitly preserving legitimate content-quality critique of a thin single slide ("A thin or underspecific single slide is still a fair critique — 'this needs another slide' is not."). Deliberately narrow, per the request: this suppresses the one false complaint category, not critique quality generally.
- `refine_post()` (`generator.py`) gained a backstop in its own prompt, restating the exact fixed slide count/roles and saying explicitly that it overrides anything the critique implies to the contrary — added because the live evidence showed the model overriding its own system-prompt-stated constraint once already; stating it only once, in the system prompt, wasn't reliably strong enough on its own.

**Tests added (`test_generator.py`, 4 new, 126 total):** `critique_post`'s prompt states the fixed shape correctly for both a 4-slide carousel and a 1-slide single_image brief, using the real `roles` list each time; the narrow-scope claim is itself asserted (the "thin single slide is still a fair critique" sentence must be present, not just the prohibition); `refine_post`'s prompt carries the backstop text with the correct slide count; and a normal-path regression check (critique says "no changes needed" → refine returns the draft unchanged, same slide count) confirms the fix didn't touch the happy path. Full suite: **126/126 passing**.

**Live re-verification, not just unit tests — same methodology as the original investigation, direct before/after comparison:**
- **Before (previous session, real API calls):** 5/12 failures (~42%) on `single_image` draft→critique→refine, all five showing the identical "critique complains about slide count → refine complies" signature.
- **After (this session, real API calls, same topic pool, calling the actual fixed `draft_post`/`critique_post`/`refine_post` functions directly rather than hand-rolled prompt strings):** first batch **0/12 failures**; a second, differently-seeded batch of 8 more (after one transient, unrelated `anthropic.OverloadedError: 529` on an angle-sampling call — retried, not a real signal) came back **0/8**. **0/20 total**, against a consistent ~25-42% rate across two independent prior batches (this investigation's 5/12, and #28's original 20-trial baseline that first established the ~1-in-4 rate). If the true failure rate were still ~25%, seeing 0/20 by chance is roughly 0.3% likely — a real, statistically meaningful drop, not sampling noise.

**Targeted follow-up check: does the narrow-scope claim actually hold, not just by design intent?** None of the 20 live trials' critique text was saved for inspection (only pass/fail was logged), so rather than assume by absence of evidence, two deliberate trials forced genuinely weak, generic single-slide drafts through the real `critique_post()` — one poetic-register (a flat "you are enough, everything will work out" quote plus a "#blessed" caption), one direct-register (a stat slide with "MANY" standing in for an actual number, ungendered generic content, a "nobody is perfect and that's okay!" caption). Both drafts are real single-slide briefs — no slide-count problem exists in either. **Both got substantive, specific content critique in return**: explicit "fake positivity" / forbidden-list flags, missing gendered specificity, zero concrete scene, no actionable takeaway, failure to actually deliver the stated approach (`question_reflection`/`common_mistakes`) — and neither critique mentioned slide count or structure anywhere. Confirms the fix suppresses exactly the one false complaint category and leaves real content critique fully intact, directly rather than by design intent alone.

**Not a blueprint deviation** — a prompt-correctness bug fix, closing a real gap between what the brief's shape actually is and what the critique step was allowed to imply about it; no design decision reversed.

---

## 38. PicksStore persistence gap (flagged in #33, never chased) — investigated fully, classified as deferred, low-stakes

**What it is.** `PicksStore` (`engine/selector.py:62-82`) is unconditionally file-backed — `.cache/picks.json` on Railway's ephemeral filesystem, no Supabase branch at all. This is unlike `MemoryStore`/`brand_kit`/`image_cache`/`audit_log`, which are all Supabase-backed with RLS locked to `service_role` per #34's pattern. First flagged as a discrepancy in #33 ("`PicksStore`... is real but unconditionally file-backed — no Supabase branch, unlike `MemoryStore`... noted, not chased further") but never investigated further until today.

**Findings.** `PicksStore` holds one JSON blob per date: a `DailyPicksResult` — 3 `DailyPick` records (`topic_id`, `topic_name`, `category`, `source_type`, `approach`, `mood`, `angle`, `hook`, `thumbnail_concept`, `awareness_day_name`) plus a `rerolls_used` counter. On a Railway restart, this file is wiped. Traced what a recompute after loss actually does: topic *selection* is deterministically reproducible (`random.Random(target_date.isoformat())` — same date, same topics/memory data ⇒ same 3 topics), but `angle`/`hook`/`thumbnail_concept` come from real, unseeded LLM calls (`generate_angle`/`_generate_pitch`) and get silently rewritten to different wording on recompute — she could see today's picks change under her with no action on her part. `rerolls_used` also resets to 0, quietly lifting the `MAX_REROLLS_PER_DAY` cap. Confirmed nothing downstream reads from `PicksStore`: export and voice-compounding both key off `MemoryStore`/`memory_id`, never a `DailyPick` — anything she's actually acted on (generated, edited, exported) already lives in `MemoryStore`, which is Supabase-backed and unaffected by this gap. Grepped `docs/logbook.md` for `picks`/`selector` — no incident has ever been tied to this; it's been a theoretical risk since #33, never observed in practice.

**Decision.** Classified as real-but-low-stakes: suggestion-tier state (today's 3 picks + reroll count), not lost work — nothing she's committed to is at risk. Migration scope, if picked up later, is already known and small, mirroring `MemoryStore`'s existing `Path | None` pattern exactly: a `daily_picks` table in `schema.sql` (RLS-locked the same way as the other four tables), `fetch_daily_picks()`/`upsert_daily_picks()` in `db/supabase.py`, and changing `PicksStore.__init__`'s default from `path: Path = PICKS_PATH` to `path: Path | None = None` with a `None`-branch in `get()`/`save()` — three files, no call-site or test changes needed (`routes/picks.py` already constructs `PicksStore()` bare; tests already pass an explicit `path=`). **Explicitly deferred, not fixed, per this decision** — no code touched.

**Closing the loop, per the standing rule this session added to `CLAUDE.md`:** this entry's status is "deferred," not "fixed" or "declined" — if it's picked up later, that decision needs to come back and close this entry the same way #30/#32 got corrected, not be left as the last word here indefinitely.

**Not a blueprint deviation** — an infrastructure-parity gap under a documented, deliberate decision to leave it, not a design decision reversed.

---

## 39. OPEN, EXPERIMENTAL — carousel-only "v1" content-voice change: connected micro-essay arc, replacing the generic quality checklist for carousel

**Status: active experiment, not yet verified against real output — implementation and
documentation only, no live `/generate` calls run as part of this entry. Needs the same
"close the loop" treatment (per the standing `CLAUDE.md` logbook-discipline rule) once
evaluated against real generations — do not treat this entry as settled until a follow-up
confirms or reverts it.**

**Why:** direct creator feedback that carousel output felt fragmented — no single
narrative throughline across a carousel's slides, each slide instead independently
satisfying the same generic quality checklist (specificity/actionability/saveability)
rather than the whole post building one connected idea. Nothing in the prompt inventory
this session's read-only review surfaced was a bug — draft/critique/refine already
operate on the whole post as one JSON object per call, with no per-slide isolation in the
main pipeline (see that review) — so this is a content-voice change, not a pipeline-shape
fix: the generic per-slide-satisfying checklist itself was identified as the actual
cause of "list of related points" output, not a coherence gap between slides.

**Scope — carousel only, everywhere, gated on `format == Format.CAROUSEL`.**
`single_image` is deliberately, completely untouched by every part of this change,
pending a separate future decision on whether to extend it there at all.

### 1. Approach pool restriction

`taxonomy/approaches.py` gained `CAROUSEL_V1_APPROACHES = [Approach.STORY,
Approach.QUESTION_REFLECTION]`. `angle_engine.py::sample_cell()` gained an
`elif format == Format.CAROUSEL` branch sampling only from this 2-approach pool, ahead of
the existing unrestricted `else` (which still covers both `format=None` — the daily-picks
pitch path that doesn't know format yet, per #26 — and, previously, carousel itself).
`format == Format.SINGLE_IMAGE`'s branch (#26's safe pool, #28's quote/stat narrowing) is
untouched, verbatim.

**The other 6 approaches (`educational`, `myth_vs_fact`, `checklist`, `stat_research`,
`framework`, `common_mistakes`) remain fully defined in code** — in `Approach`, in
`APPROACHES`, in `_APPROACH_DEFINITIONS`, in `TEACHING_BODY_APPROACHES` — nothing about
them was removed or altered. They are simply unreachable for carousel's sampler while
this experiment runs; `single_image` and the daily-picks pitch path can still reach all
8 exactly as before.

**Verified (local only, no LLM calls):** 300 seeded trials of `sample_cell(format=
Format.CAROUSEL)` reached only `{story, question_reflection}`; 300 trials each of
`format=Format.SINGLE_IMAGE` and `format=None` were unchanged from pre-#39 behavior
(4-approach safe pool and full 8-approach pool respectively). Full backend suite:
**126/126 passing**, no regressions.

### 2. Shared system prompt branch (`_brief_system_prompt`, `generator.py`)

Added an `if brief.format == Format.CAROUSEL` branch that replaces
`_SPECIFICITY_INSTRUCTION` / `_ACTIONABILITY_INSTRUCTION` / `_SAVEABILITY_INSTRUCTION` /
`_CAPTION_INSTRUCTION` with three new carousel-only constants, verbatim as specified:

**New arc instruction (carousel only):**
> This post is one micro-essay, not a list of related points. Every slide stays with a single anchor — one concrete, real, specific thing drawn from history, culture, another language, nature, or literature: a tradition, a custom, an etymology, a philosophical idea, a moment from someone's real life. Favor an anchor that carries its own specific word or phrase from another era, culture, or discipline when one genuinely fits — this is what gives the post its editorial, researched feel, not generic inspiration. Never introduce a second, unrelated example partway through. Deepen the one you opened with instead of moving to a new one.
>
> Open on the anchor itself, named plainly, by slide 1 or 2 — concrete scene-setting is fine, abstract framing is not. Spend a slide or two with the anchor alone, on its own terms, before turning to the reader at all. Make one or two turns toward the reader or the human condition, no more, each carried by a tentative word — "I wonder," "perhaps," "maybe," "somewhere along the way." Do not let this language become the default register of every slide. Once a turn has landed, the following line can state the reframe more plainly again. Close on an image or a general truth that lingers — never advice, never an instruction, never a command aimed at "you." Let the reader draw the connection to their own life themselves.
>
> Biographical or factual specifics that aren't independently verifiable get a soft hedge ("seemed to," "known for") rather than being stated as flat fact.
>
> Write in plain, declarative sentences everywhere except the one or two pivot points.

**Caption instruction override (carousel only, replaces "hook only, never a restatement"):**
> The caption mirrors the whole post's arc in prose — the same anchor, the same movement from observation to reframe. It is a second, complete telling of the same micro-essay, not a summary, teaser, or restatement.

**Specificity/actionability/saveability override (carousel only):**
> This post does not need to give the reader something to do. A closing reflection or an open question is just as valid an ending as a concrete action step. Do not force advice or a takeaway if the anchor's reframe doesn't call for one.

`single_image` briefs take the `else` branch — all four original instructions, verbatim,
unchanged. Since `draft_post`/`critique_post`/`refine_post` all call the same
`_brief_system_prompt()`, this one branch point is what every carousel generation call in
this experiment sees.

**Verified (local only):** built one `Format.CAROUSEL` and one `Format.SINGLE_IMAGE`
`ContentBrief` from the same fixture and diffed the two rendered system prompts — the
carousel prompt contains the new arc instruction and the v1 caption text and does **not**
contain the old caption instruction text; the single_image prompt contains the original
caption and specificity instructions verbatim and does **not** contain the arc
instruction. No API call made.

### 3. Critique task prompt branch (`critique_post`, `generator.py`)

Added the same `if brief.format == Format.CAROUSEL` gate. For carousel, the existing
`specificity_instruction` / `actionability_instruction` / `saveability_instruction`
checks are replaced with one new checklist, verbatim as specified:

> Confirm the post stays with one anchor throughout the whole carousel — flag it only if a new, unrelated example or point appears after slide 1. Confirm the anchor is named plainly by slide 1 or 2, without turning to the reader first. Confirm tentative language ("I wonder," "perhaps," and similar) appears once or twice at most, not on every slide. Confirm no slide addresses the reader directly with an instruction or command. Confirm the caption is a full second telling of the post's arc, not a hook, teaser, or summary. A closing reflection or open question, with no explicit action step, is acceptable and should not be flagged as a missing takeaway.

Everything else in `critique_post` — the citation check, the logbook #37 shape
instruction, the kicker check, the approach-fidelity check, the voice check — is
unchanged for both formats; only the specificity/actionability/saveability triple is
swapped for carousel. `single_image` critique is completely unchanged.
`refine_post` itself required no direct edit: it consumes whatever `_brief_system_prompt()`
and `critique_post()` already produced, so it automatically inherits the carousel branch
through those two functions without any of its own logic changing.

### Not done, deliberately

No live `/generate` call, and no change to `_APPROACH_DEFINITIONS['story']` /
`['question_reflection']` (the existing one-line structural definitions for those two
approaches are untouched — the new arc instruction sits alongside them, not in place of
them). Verification against real model output is explicitly a separate next step, not
part of this entry.

**Blueprint deviation — yes, explicitly.** This is a deliberate, carousel-only departure
from the approach library (blueprint Section 5) and from the caption/content-quality
instructions as implemented, made in direct response to creator feedback about output
quality, not a bug fix. `docs/blueprint.md` Section 5 (the `APPROACHES` list) and Section
6 (the caption/package rule) were annotated in place — not rewritten — pointing back to
this entry, same pattern as logbook #30's inline note.

### Round 1 — real-output review, 5 real `/generate`-pipeline calls, 3 bugs found

**Status update: still OPEN/EXPERIMENTAL — this round found problems, it did not close
the loop.** Ran real, live `draft_post`/`critique_post`/`refine_post`/`generate_angle`
calls (real Anthropic API, no mocking, no rng seeding) against the 5 real topic ids in
`topics.yaml` whose name matches "Boundaries" or "Rest" case-insensitively — confirmed by
grep to be exactly `mindset-boundaries`, `career-boundaries`, `relationships-boundaries`,
`mindset-rest`, `wellness-rest` (5 pairs, not just the one-per-name assumption). No
crashes, no JSON-parse failures, no slide-count/shape drift in any of the 5 runs. Approach
pool restriction held live: only `story` (2/5) and `question_reflection` (3/5) were ever
sampled, matching the local sampling test from this entry's initial implementation.

**Three real problems surfaced, purely from reading the captured output — no quality
judgment made yet, per explicit instruction that judgment is a separate step:**

1. **`critique_post`'s output was truncated by `max_tokens=500` in 5 of 5 carousel
   calls.** Every captured `critique_text` cut off mid-sentence or mid-word (character
   lengths 1359–1496). The carousel checklist added by this entry replaced 3 short
   check-instructions with one longer one, on top of the existing citation/shape/
   kicker/approach/voice checks — the same 500-token budget as before was no longer
   enough to let the model finish.
2. **Critique repeatedly flagged the closing slide's `cta` field** (3 of 5 runs) as
   generic/engagement-bait — but `ClosingSlide.cta` is hardcoded from
   `brand_kit.signature_cta` in `_build_slide()`, never model output, so this was pure
   wasted critique-budget on something `refine_post` structurally cannot act on (and,
   confirmed by diffing draft vs. refined output, never did).
3. **Kicker/arc tension and anchor-word drift, found by reading the actual text:** the
   v1 arc instruction's "dwell with the anchor alone before turning to the reader" rule
   doesn't distinguish the cover's kicker (whose established job, from before this
   experiment, is to gesture toward the reader) from the body slides — creating an
   unintended tension the arc instruction never resolved. Separately, in
   `career-boundaries`'s draft, the cover named one anchor word (`NIYO-NIYO`) while the
   body introduced a different one (`enryo`) for what was meant to be the same anchor —
   critique caught this and refine fixed it, but the arc instruction itself said
   nothing that would have prevented the drift in the first place.

### Round 1 — fixes applied

1. **`critique_post`'s carousel branch max_tokens raised 500 → 800.** single_image's
   max_tokens left at 500, unchanged — see the CTA-instruction note below for why.
2. **New unconditional instruction added to `critique_post`'s prompt, both formats
   (verbatim, exactly as specified):**
   > Do not evaluate or flag the closing slide's cta field. It is a fixed brand value from brand_kit.signature_cta, not model-generated, and cannot be changed by refine.

   Decided **not** to bump single_image's `max_tokens` for this addition: the
   instruction tells the model to skip a check, not perform an additional one, so it
   should shorten expected output rather than lengthen it — noted here rather than
   applied speculatively.
3. **Appended (not replacing) to the existing carousel-only v1 arc instruction, verbatim:**
   > The "dwell with the anchor alone before turning to the reader" rule applies to the body slides. The cover's kicker may still gesture toward the reader as its own hook — that is its separate, established job and is not a violation. If the anchor has a specific name or term, use that exact same word on the cover headline as when it's introduced in the body — don't invent a second name for the same anchor.
4. **Appended (not replacing) to the existing carousel-only critique checklist, verbatim:**
   > Confirm the closing slide lands on a declarative image or general truth, not a literal question — this holds even for the question_reflection approach. That approach is satisfied by the post orienting around a genuine open question somewhere in its arc; the final line itself should not be a question mark.

Full backend suite re-run after all four changes: **126/126 passing**, no regressions.

### Round 2 — real-output re-verification, same 5 pairs, fixes only partially held

**Re-ran real, live `/generate`-pipeline calls (same method, same 5 topic ids) after
applying the round-1 fixes. Two of the four fixes did not fully hold in practice —
reported plainly, not glossed over:**

- **CTA fix: held completely.** 0 of 5 critique texts mentioned "cta" in any form
  (round 1 was 3 of 5). Full success.
- **Critique truncation: only partially fixed.** 2 of 5 critiques now complete cleanly
  (`career-boundaries`, `relationships-boundaries` — both end on a finished sentence).
  The other 3 (`mindset-boundaries`, `mindset-rest`, `wellness-rest`) **still truncate
  mid-sentence or mid-word at the new 800-token ceiling** — e.g. `mindset-boundaries`
  cuts off inside an unclosed quotation (`"...Caption ends on declarative image
  ("Their comfort was never a`), `wellness-rest` cuts off immediately after a checklist
  heading with zero content under it. 800 tokens raised the ceiling but did not clear
  it — a further increase or a shorter checklist is still an open question, not
  resolved by this round.
- **Closing-stays-declarative fix: held in 3 of 5, broken in 2 of 5.** `career-boundaries`,
  `relationships-boundaries`, and `mindset-rest` all kept a declarative closing line, no
  question mark. But `mindset-boundaries` and `wellness-rest`'s refined closing slides
  **both ended in a literal question mark** — the exact anti-pattern the new instruction
  was meant to stop. In `mindset-boundaries`'s case this happened despite critique itself
  correctly judging the *draft's* closing as "declarative, not a question. Passes." —
  `refine_post` overrode a slide critique had explicitly passed, seemingly in an attempt
  to address a separate, valid complaint ("the real question-work happens only in the
  caption... thin delivery of the approach on the carousel itself") by pushing an
  explicit question onto the closing slide instead. The new instruction constrains what
  critique is told to check; it does not fully constrain what refine does with a
  complaint that wasn't actually asking for that particular fix.
- **Anchor-word consistency: held in 4 of 5 refined outputs, one ambiguous case, and one
  instructive draft-stage catch.** `mindset-boundaries` (AMAE), `career-boundaries`
  (NEMAWASHI, after refine), `mindset-rest` (UKIGUMO), and `wellness-rest` (NITTAAQTUQ)
  all have the literal cover headline word reappear in the body text. `career-boundaries`
  is the clearest confirmation the new instruction is doing real work: its *draft* had
  the exact mismatch this instruction targets (cover `NINSHITSU`, body `nemawashi`) —
  critique caught it explicitly by name and refine corrected the cover to `NEMAWASHI` to
  match. The draft-stage instruction didn't stop the model from drifting once, but the
  critique/refine safety net caught and fixed it before it reached final output.
  `relationships-boundaries` is a genuine ambiguous case: the cover headline
  (`NOLI ME TANGERE`) never literally reappears in the body text in either draft or
  refined version — the body continues the same Mary Magdalene/garden narrative without
  restating the Latin phrase itself. Whether that counts as compliant (same anchor,
  narrative continuity) or a violation (the literal term never recurs) wasn't judged
  here — flagged for the next review pass.

**Status: still OPEN/EXPERIMENTAL after two real-output review rounds.** The CTA fix is
confirmed solid; the other three fixes are partial, not complete — critique truncation
and refine's closing-question override both need a further pass before this can be
considered settled, and the `relationships-boundaries`-style ambiguous anchor case needs
an explicit call on what the instruction actually means. Per this project's standing
logbook-discipline rule, this entry's status must be revisited again once whatever
happens next (another fix round, or a decision to accept the current partial state) is
known — it should not be left open indefinitely without a closing update.

### Round 3 — diagnosis before fixing, plus two more fixes and a re-verification

**Diagnosis requested for the closing-question override, done before touching any code.**
Read `_APPROACH_DEFINITIONS["question_reflection"]` verbatim
(`generator.py`): *"poses a genuine, specific question the reader is meant to sit with —
not a rhetorical throwaway — with the post's content oriented around exploring it."*
**Hypothesis not confirmed** — this contains no instruction to conclude, end, or close on
a question; it's a content-orientation rule with no opinion on which slide should carry
it. Read the actual prompts each function sends to find the real mechanism instead of
guessing: `_CAROUSEL_V1_SPECIFICITY_ACTIONABILITY_SAVEABILITY_INSTRUCTION` — the
carousel-only override living in the **shared system prompt** that `draft_post`,
`critique_post`, *and* `refine_post` all read on every call — explicitly says *"A closing
reflection or an open question is just as valid an ending as a concrete action step."*
That's a standing instruction framing an open question as a legitimate ending, read by
`refine_post` directly. Compounding it: round 2's closing-declarative fix was added only
to `critique_post`'s own task-prompt checklist (a thing for critique to check), never
restated to `refine_post` as an explicit backstop the way the slide-count rule got one
(per #29's pattern) — and in both round-2 failures, critique's truncated response never
even reached that checklist line, so refine had zero explicit "stay declarative" signal
in either failing case. **No speculative fix applied for this mechanism this round** —
reported back rather than guessed at, per explicit instruction; the shared system
prompt's "open question is a valid ending" line is untouched.

**Two further fixes applied, independent of the above diagnosis:**

1. **Critique's carousel `max_tokens` raised 800 → 1200.** Round 2 showed 800 wasn't
   enough (3 of 5 still truncated). single_image stays at 500, unchanged.
2. **Carousel checklist tightened, not just given more room.** Consolidated from 8
   sentences / 963 characters down to 4 sentences (3 `Confirm...` + 1 acceptance
   clause) / 790 characters — same substantive checks (anchor discipline, tentative-
   language frequency, direct-address, caption-mirror, closing-declarative,
   no-forced-takeaway), fewer words spent restating them. Before/after both on record
   in the code's own history; the tightened version is now what ships.
3. **Anchor-word carve-out added**, appended to the existing "use the exact same word"
   sentence in the v1 arc instruction: *"This applies to a single coined term or named
   concept (e.g. amae, nemawashi). If the anchor is a quote or phrase rather than a
   single term (e.g. \"Noli me tangere\"), the body doesn't need to restate it verbatim
   as long as the narrative stays visibly anchored to the same quote/scene throughout."*
   Directly answers `relationships-boundaries`'s round-2 ambiguous case.

Full backend suite re-run after all changes: **126/126 passing**, no regressions.

**Round 3 re-verification, same 5 real pairs, real Anthropic API:**

- **Critique truncation: fully resolved, 5 of 5.** Every critique now ends on a
  complete, punctuated sentence — no mid-word or mid-quote cutoffs, a clear
  improvement over round 2's 2-of-5.
- **CTA fix: still holding, 5 of 5, more precisely confirmed this round.** Two
  critiques contained the literal substring "cta" — `mindset-boundaries`'s was "no
  bossy CTAs" (an unrelated forbidden-list check), and `mindset-rest`'s explicitly said
  *"Caption CTA line (...) is fixed per instructions, not evaluated"* — i.e. the model
  itself confirming compliance, not violating it. Zero actual flags of the field.
- **Closing-declarative: 5 of 5 held this round** (was 3 of 5 in round 2) — no refined
  closing slide contained a question mark. In every one of the 5, critique's now-
  complete response explicitly reached and stated a "declarative, compliant" verdict on
  the closing, and refine respected it every time (in one case, `mindset-rest`,
  critique instead flagged the closing as reading like a soft command — "Maybe it's
  time to close the book" — and refine correctly rewrote it to stay declarative
  without turning it into a question). **Caveat, stated plainly and not oversold:**
  the underlying mechanism identified in this round's diagnosis (the shared system
  prompt's "open question is a valid ending" line) was not changed, and round 2's own
  `mindset-boundaries` failure happened even when critique explicitly passed the
  closing as declarative — so this round's clean result plausibly reflects critique now
  always finishing and clearly stating its verdict (rather than truncating before or
  after the relevant line), not a guaranteed structural fix. Five real runs is not a
  large enough sample to rule out recurrence.
- **Anchor-word carve-out: not exercised by this round's sample.** All 5 pairs this
  round sampled single coined-term anchors (`AMAE`, `PO`, `KEEPER`, `TALLY`, `KEIRO`) —
  none produced a quote-type anchor like round 2's "Noli me tangere" case, so the new
  carve-out clause had no real case to prove itself against this round. Confirmed
  present in the rendered prompt by local check (no API call) before the live run.
  The underlying "same exact word" rule it's attached to worked precisely as intended
  in `career-boundaries`: the draft's cover (`KATOMBI`, a fabricated word never used in
  the body) was caught explicitly by critique's now-complete response ("the cover
  headline says 'KATOMBI' but the body never uses this word or confirms it... this
  reads as a factual overreach"), and refine replaced it with a real, verifiable term
  (`PO`) that the body does use — the check didn't just catch a naming drift, it
  caught an outright fabrication.

**Status: still OPEN/EXPERIMENTAL — closer, not closed.** Three of four rounds of fixes
now hold cleanly (CTA, truncation, and — with the caveat above — closing-declarative);
the anchor carve-out is implemented and locally verified but unexercised by real output
so far; and the diagnosed root cause of the closing-question override (the shared
system prompt's own "open question is a valid ending" line) remains unaddressed by
choice, reported rather than guessed at. Not ready to close the loop yet — worth one
more round with a larger or targeted sample (specifically forcing a quote-type anchor,
and/or deciding whether to touch the shared system prompt's ending-flexibility line) before
this moves to an actual quality read rather than further structural debugging.

### Round 4 — a direct backstop for the closing-declarative rule in `refine_post` itself

**Hardening, same precedent as #29/#37 explicitly:** round 3's diagnosis found the
closing-question override wasn't caused by `_APPROACH_DEFINITIONS["question_reflection"]`
(ruled out directly, no instruction to end on a question there) but by two things acting
together — the shared system prompt's carousel-only line *"A closing reflection or an
open question is just as valid an ending as a concrete action step,"* read by
`refine_post` on every call, and the fact that the round-2 closing-declarative fix was
only ever stated to `critique_post` (as something to check), never to `refine_post`
directly. The slide-count rule already has exactly this two-layer pattern (a system-
prompt statement plus a restated backstop in `refine_post`'s own task prompt, from
#29/#37) — the closing-declarative rule didn't, until now. `refine_post` gained a second,
independent statement of the rule, carousel-only, verbatim as specified:

> Keep the closing slide declarative — an image or general truth, not a literal question — even if the approach is question_reflection, and regardless of what critique's note does or doesn't say about the closing specifically.

Confirmed locally (prompt-string capture, no API call, `FakeLLM` swallowing the response
so only the constructed prompt is inspected) before any live call: present verbatim in
`refine_post`'s rendered prompt for a `Format.CAROUSEL` brief, completely absent for a
`Format.SINGLE_IMAGE` brief. Full backend suite re-run after the change: **126/126
passing**, no regressions.

**Live re-verification:** one real `/generate`-pipeline call (`wellness-rest`, chosen
from the same 5 pairs used throughout this entry) sampled `question_reflection` on the
first attempt — the only approach this bug ever affected — so the 2-attempt cap wasn't
needed. Draft closing: *"Boredom isn't empty. It's the only room quiet enough for you to
hear yourself again."* Critique's verdict, verbatim: *"**Closing slide:** Declarative,
not a literal question — correct per rules. Good line, earns its place as a lingering
image/truth rather than advice."* Critique separately flagged the approach as
under-delivered and suggested sharpening the caption's "I wonder" musing into an actual
question. Refine's final closing slide: **unchanged**, still *"Boredom isn't empty. It's
the only room quiet enough for you to hear yourself again."* — declarative, no question
mark. Refine instead added the suggested question to the **caption** ("When did you last
let a day mean nothing — no output, no permission slip, no reason you could explain to
anyone?"), correctly following critique's actual suggestion (sharpen the caption) rather
than reaching for the closing slide the way it did twice in round 2.

**Status: structurally settled enough to stop touching for now.** All four round-2/3/4
fixes (CTA, truncation, closing-declarative, anchor-word carve-out) are implemented and
have each been observed holding in live output at least once, with the closing-
declarative rule now backed by the same two-layer system-prompt-plus-refine-backstop
pattern that #29/#37 already proved reliable for the slide-count rule. Still genuinely
open, not closed outright: sample sizes remain small (this round's confirmation is one
real run), the anchor carve-out still has zero real quote-type-anchor exercise, and the
underlying system-prompt line this round's diagnosis identified is still untouched by
design. But structural debugging has reached a reasonable stopping point — the next
useful step is the actual quality read this entry has been deferring since round 1, not
another round of mechanical fixes.

### Round 5 — a second reader-address leak, found by reading the actual prose, not a bug report

**Worth recording explicitly: this one wasn't found by structural testing.** Every prior
round's findings came from a crash, a truncated response, a literal question mark, or
some other machine-checkable signal. This one came from directly reading round 1's
captured `mindset-rest`/`NIKSEN` output line by line: `refine_post` had appended an
unhedged, direct question — *"What would it take for you to believe that?"* — onto the
body slide that introduces the anchor (`niksen`) itself, the exact slide the v1 arc
instruction says should dwell on the anchor alone before any reader-turn. No test in this
project's suite, and no structural check added in rounds 2–4, would have caught this —
it required reading the sentence and recognizing that a "you" and a question mark had
landed somewhere the arc instruction never sanctioned.

**Diagnosis, done before any fix, per standing instruction not to assume:** read
`_APPROACH_DEFINITIONS["question_reflection"]` (unchanged since round 3 — *"poses a
genuine, specific question the reader is meant to sit with... with the post's content
oriented around exploring it"*) and `critique_post`'s approach-fidelity wrapper around it
(*"Separately check whether the post's structure actually delivers the approach... as
defined above"*). **Confirmed: neither specifies where in the post that question should
live.** This is the same underlying ambiguity round 3 diagnosed for the closing-question
override — just manifesting in a different slide this time, because nothing tells refine
where the "correct" slide is, only that a question must exist "somewhere."

**Fix, same three-part pattern as the closing-question fix (rounds 2–4), applied to a
different location this time:**

1. **Arc instruction (system prompt, carousel-only)** — appended, verbatim:
   > The slide(s) spent dwelling on the anchor alone must contain no reader-address of any kind — no "you," no question, nothing aimed at the reader — full stop. If the approach requires a genuine question somewhere in the post, it belongs in the caption or, at most, the one designated pivot slide later in the carousel, phrased with tentative language, never as a blunt question dropped into the anchor's introduction.
2. **Critique checklist (carousel-only)** — appended, verbatim:
   > Confirm no body slide other than the correctly-placed pivot slide addresses the reader directly — via "you" or a posed question — before the anchor's dwelling slides are complete. If question_reflection's required question isn't yet present anywhere in the post, the caption is the correct place for it, not an early body slide.
3. **`refine_post` backstop (carousel-only, third instance of the #29/#37 two-layer
   pattern in this entry)** — appended, verbatim:
   > If you need to add a genuine question to satisfy the question_reflection approach, add it to the caption — not to a body slide that's meant to be dwelling on the anchor alone.

Confirmed locally, all three, before any live call (direct prompt-string capture via a
`FakeLLM` that swallows the response, no API call): present in the carousel-format
rendered prompt at each of the three touch points (`_brief_system_prompt`,
`critique_post`, `refine_post`), completely absent for `Format.SINGLE_IMAGE` in all
three. Full backend suite re-run: **126/126 passing**, no regressions.

**Live re-verification, one real pair with a real, plainly-reported hiccup along the
way:** the first live attempt (`mindset-rest`) sampled `question_reflection` immediately,
but `refine_post` hit the pre-existing, already-documented intermittent JSON-parse
failure class (logbook #7/#28/#29 — `"Invalid control character at..."`) — reported
here rather than silently retried, then re-run once on the same pair, which completed
cleanly. Draft and refined carousel had exactly one body slide (`"In Victorian etiquette
manuals, women were taught productive idleness — rest had to look like mending, tending,
waiting on someone."`), **verbatim identical between draft and refined** — zero reader-
address, no "you," no question mark, untouched by the refine pass. Critique's own
verdict on it, verbatim: *"slide 2 dwells with the anchor but is the only body slide, and
it's clean — no reader address, good."* Critique separately flagged the caption's
existing question as too quickly self-resolved ("reads more like a resolved reflection
than a live question left open") and asked refine to sharpen it. Refine's rewritten
caption did exactly that — restructured around *"I wonder how much of that ledger is
still open. Whether the guilt... whether that guilt is even about the workouts at all...
Maybe it's just worth sitting with — whose voice that really is, and what it would take
to stop keeping score"* — genuinely open-ended, phrased as indirect/embedded questions
("whether...", "what it would take to...") rather than a literal "?" character, which is
worth noting plainly rather than glossed over: the fix landed the question in the
correct place (the caption, not the body slide, not the closing), even though the
specific phrasing this run produced wouldn't trip a naive "does it contain a '?'" check.
The closing slide (`"Rest was never late. The debt was invented."`) stayed unchanged and
declarative throughout, confirming round 4's fix is still holding alongside this one.

**Status: still OPEN/EXPERIMENTAL, structural debugging continues to turn up real
findings on direct review, not just on machine-checkable signals.** This round is a
concrete argument for reading actual output, not just running structural checks, before
calling this entry settled — the closing-question and body-slide-question leaks are
different bugs with the same root ambiguity, found on two separate passes through the
real text. One real confirmation this round, same small-sample caveat as every prior
round. Worth at least one more pass specifically hunting for a third location the
question could leak to (a mid-carousel pivot slide getting an unhedged, un-tentative
question, for instance) before concluding the underlying approach-fidelity ambiguity is
fully contained rather than just found in two of however many places it could surface.

### Round 6 — anchor-lock and hedge-floor fixes, found through real organic use of the live app

**A change in how this experiment is being verified, worth stating explicitly.** Every
prior round's findings and re-checks came from sessions here — either a controlled
5-pair test batch or a direct real `/generate`-pipeline call driven from this session.
This round's two findings came from somewhere different: **real, organic use of the
live deployed app**, not anything run from this session. Verification for this round is
**deliberately deferred to that same live, organic use going forward**, not another
CC-driven test batch — a decision made explicitly here, not a gap. Implementation and
documentation only this round; no `/generate` calls were run from this session as part
of applying these two fixes.

**Finding 1 — anchor swap.** A real generation on `mindset-perfectionism` (headline
`PERSIAN FLAW`, going by the angle's own material) abandoned the angle's own concrete
anchor — a specific email-rewriting story — partway through, replacing it with an
unrelated historical anchor (Persian carpet weaving) with no bridge between the two,
leaving the hook, body, and closing disconnected from each other. Likely cause: the
existing "favor an anchor that carries its own specific word or phrase from another
era, culture, or discipline when one genuinely fits" sentence (added in the original
round-1 arc instruction) was incentivizing a swap toward whatever felt most evocative,
rather than requiring the model to stay with the anchor the angle itself had already
established.

**Finding 2 — missing hedge.** A real generation on `mindset-boundaries` (headline
`KIVELA`) produced a post with zero tentative-language moments anywhere — no "I
wonder," no "perhaps," nothing — skipping the anchor-to-reader pivot entirely. The
existing hedge-frequency rule ("one or two turns... no more") was a ceiling with no
floor; nothing in it, or in critique's checklist, would have flagged a post that never
pivoted at all as a defect.

**Fixes, all carousel-only, all verbatim as specified:**

1. **Arc instruction (system prompt) — anchor-lock**, appended directly after the
   existing "favor an anchor..." sentence:
   > This must still be the same anchor the angle itself already establishes — its specific concrete detail, moment, or thing. Do not replace it with a different anchor partway through the post, even a more evocative or historical one. If a historical, cultural, or linguistic reference genuinely adds something, it must be explicitly and clearly connected in the text to the angle's own anchor — the reader should never have to infer the link between two separate images on their own. One anchor, established once, carries the whole post.
2. **Arc instruction (system prompt) — hedge floor**, added next to the existing
   hedge-frequency ceiling:
   > At least one tentative moment ("I wonder," "perhaps," "maybe," or similar) must appear somewhere in the post — in a body slide, the closing, or the caption. The pivot from anchor to reader cannot be skipped entirely.
3. **Critique checklist**, both fixes, appended to the existing carousel checklist:
   > Confirm the post never introduces a materially different anchor from the one the angle itself established — flag it if a new historical, cultural, or object-based reference appears without being explicitly connected back to the angle's own concrete detail. Confirm at least one tentative moment ("I wonder," "perhaps," "maybe," or similar) appears somewhere in the post — flag it if the pivot from anchor to reader is skipped entirely, not just if it's overused.
4. **`refine_post` backstop** (fourth instance of the #29/#37 two-layer pattern in
   this entry), appended to `refine_post`'s own task prompt:
   > If critique flags an anchor swap, fix it by either returning to the angle's own original anchor or explicitly connecting the new reference back to it in the text — don't leave two disconnected images in the same post. If critique flags a missing hedge, add exactly one tentative moment at the natural pivot point — don't add more than one just because one was missing.

Confirmed locally (direct prompt-string capture via a `FakeLLM` that swallows the
response, no API calls) before anything else: all four additions present verbatim in
the rendered carousel prompt at their respective touch points (`_brief_system_prompt`
×2, `critique_post`, `refine_post`), completely absent for `Format.SINGLE_IMAGE` in all
four. Full backend suite re-run: **126/126 passing**, no regressions.

**Status: still OPEN/EXPERIMENTAL.** Implementation-only round — no live verification
attempted or claimed here. The next signal on whether these two fixes actually hold
will come from continued real, organic use of the live app, not a scheduled CC-driven
test round; that's a deliberate change in this entry's verification approach from here
on, not an oversight to fill in later.

### Round 7 — the real CTA/question slide: the first structural change in the v1 line of work

**Explicitly different in kind from rounds 1–6.** Every prior round in this entry was a
prompt-text change — wording added to the arc instruction, the critique checklist, or a
`refine_post` backstop, all operating within the existing five/six-template slide shape.
This round adds a genuine new slide type, changing carousel's slide count for the first
time (4–5, not 3–4) — done deliberately, per direct instruction to prioritize matching
the locked hand-written v1 reference format over preserving the shape locked in
`implementation-guide.md` Section 10 / `blueprint.md` Section 12.

**What was built:** a new `ConversationSlide` (`models/post.py`) — `label` (fixed:
`"🌿 Conversation for today"`), `question` (the only model-written field, the real
open question tied to the post's anchor), `invite` (fixed: `"I'd love to hear it."`) —
same fixed-field pattern as `ClosingSlide.signature/cta/handle`. `slide_roles_for()`
appends `carousel_conversation` after `carousel_closing` for every carousel brief,
unconditionally on approach (single_image completely untouched). The shared system
prompt's slide-shape block, the arc instruction (new guidance for the question field,
verbatim as specified), and the carousel critique checklist (new confirm clause,
verbatim as specified) were all updated to match. Frontend: a new
`ConversationSlide.tsx` component (masthead-pinned-top / flex:1-centered layout, same
convention as `CarouselClosing`), wired into both `SlideRenderer.tsx` (editor preview)
and `app/api/render/route.tsx` (the real PNG export route) — confirmed by direct
inspection, not assumed, the same explicit check logbook #32 did for `Masthead.tsx`.
Also wired into `app/preview/page.tsx` (now 7 templates × 3 moods) and
`app/editor/page.tsx`'s `SlideEditForm` (the `question` field is editable; `label`/
`invite` are not, matching `ClosingSlide`'s pattern).

**Ripple effects, checked rather than assumed:**
- `MemoryRecord.slides` (Supabase jsonb, added #35) round-trips the new slide type
  with **zero special-casing needed** — `db/supabase.py`'s `fetch_memory`/
  `append_memory`/`update_memory` are already fully generic (`model_dump(mode="json")`
  / `model_validate(row)` against the `Slide` discriminated union), confirmed by
  reading the actual code, not assumed from the pattern holding for prior additions.
- `routes/export.py`'s `_extract_best_line` iterates via `generator.slide_text()`,
  which gained a `ConversationSlide` branch — no special-casing needed there either.
- **Masthead number logic is unaffected** — `next_masthead_number()` counts
  `MemoryRecord`s by category/status only, never inspects `slides` at all (re-confirmed
  by reading `models/memory.py`, not assumed from #32's prior finding).
- **`brief.slide_count` needed a real fix, not just the new role appended** —
  `validator.py`'s `_check_format` compares `len(post.slides)` against
  `brief.slide_count` exactly; adding a role without updating slide-count math would
  have made every carousel post fail validation with a false "expected N, got N+1"
  error. Fixed at the source: `brief_builder.py`'s `_default_slide_count` (4→5
  teaching, 3→4 non-teaching) and `paste_link.py`'s `_SLIDE_COUNT[CAROUSEL]` (3→4) —
  paste-link carousels go through `_brief_system_prompt`'s format-only branch too
  (never through the angle engine or its approach restriction), so they get
  `carousel_conversation` exactly the same as taxonomy-driven carousels.
- **22 existing tests broke and were fixed as a direct, necessary consequence** of the
  slide-count/shape change (same classification as #26's precedent) — updated fixture
  JSON, expected role lists, and hardcoded slide counts across `test_generator.py`,
  `test_brief_builder.py`,`test_paste_link.py`, `test_validator.py`,
  `test_generate_route.py`, `test_generate_route_http.py`. One of those fixes
  corrected a latent false-positive: `test_generate_from_brief_route_handles_non_taxonomy_topic_id`
  was passing before this round for the wrong reason — its `slide_count`/draft-JSON
  fixture was already one slide short of matching real roles, silently absorbed by
  `_build_slide()`'s `.get()`-with-empty-default fallback rather than raising; now
  fixed to genuinely match.

**Local verification (no `/generate` calls, as instructed):**
- `npx tsc --noEmit`: clean, exit 0.
- Full backend suite: **127/127 passing** (126 + 1 new test —
  `test_draft_post_fills_conversation_slide_label_and_invite_from_defaults_not_llm`).
- Direct prompt-string check (no API calls): `carousel_conversation` present in the
  rendered carousel system prompt (role list, field example, and the new arc-
  instruction guidance), completely absent from the single_image prompt.
- **Rendered the new template through the real Satori path** — started a local `next
  dev` server, `POST`ed directly to `/api/render` with `template_id:
  "carousel_conversation"` and the same fixture content as the preview page: `200`,
  valid `1080×1350` PNG. A `carousel_closing` render was also re-checked as a
  regression control: still `200`, still valid. Dev server stopped afterward.

**A real bug found by that render, not by any structural check:** the fixed label's
🌿 emoji has **no glyph in this project's locked font set** (Archivo Black / Alex
Brush / Inter — `blueprint.md`'s locked Google Fonts, per `lib/fonts.ts`) and renders
as tofu (`??`) through Satori. Confirmed visually from the actual rendered PNG, not
inferred. Not fixed in this pass — reported plainly rather than altering the fixed
brand copy unilaterally; fixed in the immediate follow-up below.

**Status at the time: still OPEN/EXPERIMENTAL — and carrying a genuine structural risk
the prior six rounds didn't.** This is the first change in the #39 line of work that
isn't reversible by editing prompt strings alone; a decision to back it out would mean
removing a slide type and its ripple fixes, not just deleting a paragraph. No live
`/generate` call has been run against it — real testing happens through the live app
next, not through this session, per explicit instruction.

### Round 7 follow-up — glyph fix, verified against the real font files, not guessed

**Tested four candidates in the requested order, against the actual bundled font
files, through real `/api/render` calls — not assumed from any one of them "probably"
working:** em dash (—), middot (·), hedera/floral heart (❧), star (✦). **All four
rendered as tofu**, confirmed visually from each actual rendered PNG in turn. Before
concluding the font itself was the cause, ruled out a transmission/encoding artifact
in the test method: a plain ASCII asterisk (`*`) rendered correctly through the exact
same request path, confirming the pipeline and the test method were both fine — the
four requested candidates themselves have no glyph in this project's bundled Inter
TTF (`public/fonts/Inter-*.ttf` — appears to be a Latin-subset export with no extended
Unicode punctuation, not just no emoji coverage).

**None of the four specified candidates passed**, so a fifth, ASCII-safe option was
tried and verified rather than forcing a broken glyph through: a plain hyphen (`-`),
closest in spirit to the em dash that was first choice. Rendered cleanly, confirmed
visually. **Fixed label: `"- Conversation for today"`** (was `"🌿 Conversation for
today"`) — updated in `models/post.py`'s `ConversationSlide.label` default,
`lib/placeholder-content.ts`'s `PLACEHOLDER_CONVERSATION`, and the corresponding test
assertion in `test_generator.py`. `blueprint.md` and `CLAUDE.md`'s round-7 notes
updated to match rather than left describing the now-fixed emoji version.

**Verified, same rigor as the original finding:** each of the 4 failing candidates and
the 2 passing ones (ASCII asterisk, ASCII hyphen) rendered through a real local `next
dev` server and real `/api/render` `POST` calls, `200` responses, each PNG visually
inspected directly — not inferred from HTTP status alone. Full backend suite re-run
after the fix: **127/127 passing**. `npx tsc --noEmit`: clean.

**Not a blueprint deviation beyond what round 7 itself already is** — this is a bug
fix within the same structural addition, not a new design decision.

### Round 8 — 3 body slides, "with you," removal, follow-us relocation, anti-padding/split guidance, word tolerance

**Five confirmed, decided changes, not new findings from testing.** Unlike most
prior rounds, these came in as direct instructions rather than something surfaced
by a test batch or organic use — implementation and local verification only, same
discipline as every other round: no `/generate` calls, real testing happens live
afterward.

**1. Body slides raised 1–2 → 3, fixed regardless of approach.** Confirmed final
shape: cover, body, body, body, closing, conversation — 6 slides total.
`slide_roles_for()`'s body count is no longer derived from `brief.slide_count`
(`max(n-3, 0)`, varying 1–2) — it's now a flat `3`. This collapsed
`brief_builder.py`'s `_default_slide_count` (previously 5/4, conditional on
`TEACHING_BODY_APPROACHES`) to a flat `6` for every carousel approach — the body
*role* (`carousel_body_teaching` vs `carousel_body`) still varies by approach,
just always 3 of it now. `paste_link.py`'s `_SLIDE_COUNT[CAROUSEL]` bumped
4 → 6 to match, same reasoning as round 7's 3 → 4.

**2. "with you," removed from the closing slide.** Investigated first, as asked:
`ClosingSlide.signature` defaults to `"with you,"` in the Pydantic model itself
and is also passed as that literal string explicitly in `_build_slide()` —
**hardcoded, not a `brand_kit` field.** (`cta`/`handle`, by contrast, *were*
real `brand_kit.signature_cta`/`brand_kit.handle` fields — see #3.) Since there's
no underlying brand_kit data to preserve, the closest equivalent to "don't delete
backend data, mirror #32's display-only pattern" is: the `signature` field stays
on `ClosingSlide` and `_build_slide()` still computes it exactly as before —
`CarouselClosing.tsx` simply stopped rendering it. Verified via a real
`/api/render` call: clean render, masthead + takeaway only, no layout gap — the
`flex: 1; justify-content: center` wrapper re-centers correctly around fewer
children with no code change needed there.

**3. "Follow us..." / `@womensgrowthsociety` relocated from `ClosingSlide` to
`ConversationSlide`.** Investigated first: `cta` (`brand_kit.signature_cta`) and
`handle` (`brand_kit.handle`) **are** real `brand_kit` fields — genuinely
misplaced, not display noise. They were still landing on `ClosingSlide` because
that was the true last slide before round 7 added `carousel_conversation` after
it; nobody had moved them. Fixed as a real relocation, not a duplicate/display-only
change (unlike #2): removed `cta`/`handle` from `ClosingSlide` (Pydantic model,
`models/post.py`) and added them to `ConversationSlide`, populated in
`_build_slide()`'s `carousel_conversation` branch exactly as `carousel_closing`'s
branch used to. Frontend mirrored the same move — `CarouselClosingContent`/
`CarouselConversationContent` (`lib/types.ts`), `CarouselClosing.tsx` (stopped
rendering them), `ConversationSlide.tsx` (renders `cta` then `handle` after
`invite`, same typographic treatment — body-copy-weight sentence, tiny
letter-spaced uppercase footnote — the original `CarouselClosing.tsx` used).
Verified via real `/api/render` calls on both templates (shown above and below)
— closing shows only masthead + takeaway, nothing orphaned; conversation shows
label, question, invite, cta, and handle in one uncrowded, readable stack.

**4. Anti-padding + split guidance**, appended to the carousel arc instruction —
**adapted from a proven pattern found by auditing a separate project's carousel
mechanism, not invented fresh for this one**:
> You have three body slides — use as many as the content genuinely needs, but do not pad to fill all three, and do not force one idea across multiple slides just to use the space available. If a single slide's content has more than one distinct fact or beat genuinely competing for room — especially when a reframe depends on a contrast between two things — split it across two slides rather than compressing both into one. Each body slide should do one clear job.

This is a direct answer to raising body slides to 3 (#1): nothing about the count
change itself stops the model from padding thin content across all three, so this
guidance is what's actually meant to prevent that, not the count.

**5. 10% word-budget tolerance**, added to both the system prompt's stated cap and
critique's own enforcement of it, unconditionally for both formats (not
carousel-only, unlike #1/#4) — a real near-miss (37 vs. 30 words) during earlier
testing showed a hard cap with zero tolerance treats a trivial overage as the same
defect as a genuinely bloated slide. New `_tolerant_word_cap()` helper
(`math.ceil(cap * 1.1)`) computes the buffer once, shared by both call sites:
`_brief_system_prompt()`'s stated cap line now reads target + "with up to 10%
over ({tolerant_cap}) as an acceptable buffer, not a hard wall"; `critique_post()`
gained a dedicated `word_tolerance_instruction` restating the same tolerant number
directly, not just relying on the shared system prompt reaching critique
indirectly. **Deliberately out of scope: `validator.py`'s deterministic
`_check_format` word-count check is unchanged** — it's a hard check against the
original (non-tolerant) cap, per the literal instruction ("system prompt's stated
cap and critique's enforcement of it," not the Python validator). Flagged
explicitly rather than silently expanding scope: this means a slide within the
new LLM-facing buffer (e.g. 32 words on a 30-word cap) could still produce a
`validation_errors` entry in the app UI even though neither the system prompt nor
critique would treat it as a defect — a real, known inconsistency between what the
model is told and what the deterministic checker enforces, left for a separate
decision rather than assumed to be in scope here.

**Local verification (no `/generate` calls, as instructed):**
- Local prompt-string capture (no API calls): `slide_roles_for()` confirmed
  returning 3 body slides; anti-padding/split guidance present in the carousel
  system prompt, absent from single_image; the tolerant word cap (33, for the
  default 30-word target) present in **both** carousel and single_image system
  prompts (deliberately universal, not gated); critique's word-tolerance
  instruction and its updated (conversation-slide, not closing-slide)
  `cta_instruction` both confirmed present.
- Real `/api/render` calls for the modified `carousel_closing` and
  `carousel_conversation` templates — both `200`, both visually inspected
  (screenshots captured this session): closing clean with no orphaned gap,
  conversation showing all five of its fields (label, question, invite, cta,
  handle) without crowding.
- **22 more tests needed updating**, the same kind of mechanical, necessary
  consequence round 7's slide-count change required — `test_generator.py`,
  `test_brief_builder.py`, `test_paste_link.py`, `test_validator.py`, and
  `test_generate_route_http.py` all had hardcoded slide counts, role lists, or
  fixture JSON shaped for the old 1–2-body/cta-on-closing shape. Full backend
  suite after all fixes: **127/127 passing**. `npx tsc --noEmit`: clean.

**Status: still OPEN/EXPERIMENTAL.** Slide count is now 6 total (was 4 after round
7, 3 before that) — this round changed *shape* again on top of round 7's
first-ever structural change, not just prompt wording. Next verification step is
live, organic use, same as declared after round 6 — not another CC-driven round.

**Correction, same round, caught immediately after landing:** point 5's 10%
word-budget tolerance was applied **universally to both formats by mistake** —
inconsistent with every other v1 change in this entry, all of which are
carousel-only. Fixed in the same round: `_brief_system_prompt()`'s word-cap line
and `critique_post()`'s `word_tolerance_instruction` are now both gated on
`brief.format == Format.CAROUSEL`; single_image reverts to the original,
untolerant cap in both places, unchanged from before round 8. Separately,
`validator.py::_check_format` — the deterministic Python check actually driving
the app's "Needs a look" warning banner, not touched at all in the first pass of
round 8 — was brought into alignment with the same carousel-only tolerance, so
the visible warning and what the model is actually told now agree: a carousel
slide at 33 words (the tolerant cap for a 30-word target) no longer trips a
validation error the model was never told was a problem, while single_image's
check stays exactly as strict as it always was. Verified directly at the
boundary, not just by re-running the suite: carousel at 33 words → no error,
34 words → flagged (message now shows the effective 33-word cap, not the bare
30); single_image at 30 words → no error, 31 words → flagged (unchanged
behavior). Full backend suite: **127/127 passing**, no test changes needed.

---

## 40. LOCKED-DECISION REVERSAL — production text generation defaults to OpenAI (`gpt-5.6-luna`/`gpt-5.5`), Claude kept fully functional behind an explicit opt-in

**Symptom / trigger:** Anthropic ran out of production credits entirely — every
Claude call, cheap or strong tier, started failing
(`anthropic.BadRequestError: Your credit balance is too low...`), breaking
`/generate` end to end. Separately, real A/B testing on the isolated `/poc`
direct-write path (`docs/direct-write-poc.md` Section 9, and a further
7-trial round comparing `gpt-5.5` against a candidate `gpt-5.6-terra` model)
had already produced real evidence that `gpt-5.5` matched or beat Sonnet 5 on
anchor authenticity and voice discipline. Both facts together made this a
deliberate, evidence-based decision to reverse `CLAUDE.md`'s locked model
choice, not a stopgap patch.

**What changed:** `app/providers/llm.py`'s `LLMProvider` now wraps either
provider behind the same tier-based `complete(tier=...)` interface every
caller already used (`angle_engine.py`, `generator.py`'s draft/critique/
refine/regenerate_slide, `paste_link.py`'s summarization, `routes/picks.py`'s
daily-pick pitches). Provider is resolved once per instance, never per-call:
`LLMProvider()` (every existing call site, unchanged) now defaults to
`provider="openai"` (`LLM_PROVIDER` env var, default `"openai"`), giving
`gpt-5.6-luna` (cheap tier) / `gpt-5.5` (strong tier). The Claude path is
**fully preserved, not degraded** — `LLMProvider(provider="anthropic")` per
call, or `LLM_PROVIDER=anthropic` fleet-wide with no redeploy, both route to
the exact original models (`LLM_MODEL_CHEAP_ANTHROPIC`/
`LLM_MODEL_STRONG_ANTHROPIC`, defaulting to the original
`claude-haiku-4-5-20251001`/`claude-sonnet-5`). Same explicit-opt-in shape
the POC already used when `gpt-5.5` became its own default.

**Key decision: text generation reuses the existing production
`OPENAI_API_KEY`** (already used for GPT Image 2 hero images), not a new key
and not the isolated `OPENAI_API_KEY_POC`. Reasoning: `OPENAI_API_KEY_POC`'s
isolation exists specifically to keep an experimental, throwaway code path
from touching production credentials — that rationale doesn't apply to
production code isolating itself from itself. Reusing the existing key means
zero new secrets were needed for this migration.

**A real, previously-latent bug found and fixed in the same pass, not
assumed away:** `gpt-5.5`/`gpt-5.6-luna` spend part of `max_completion_tokens`
on invisible reasoning tokens before ever emitting visible content — the
OpenAI-side equivalent of this same file's existing
`thinking={"type": "disabled"}` fix for Sonnet 5's extended thinking, same
failure class. Confirmed live at this codebase's real cheap-tier budgets
(100–300 tokens): the entire budget was consumed by reasoning, content came
back empty. Initially assumed the strong tier's wider budgets (400–1500)
had enough headroom to not need the same fix — **disproven live**:
`critique_post()`'s real single_image budget (500 tokens) against a
realistic draft-length prompt also returned empty (500/500 tokens spent on
reasoning, 0 on content). Reasoning-token consumption scales with prompt
complexity, not a fixed per-call overhead, so no budget in this codebase's
actual range was provably safe left at the model's default.
`reasoning_effort="none"` applied unconditionally to every OpenAI call (both
tiers) fixes it — confirmed live at every real production budget (150, 300,
500, 1200, 1500): `reasoning_tokens=0`, full content returned every time.
Shipping the naive default (reasoning left uncontrolled) would have silently
broken every strong-tier call in production the first time critique ran
against a real draft.

**Verification, real trials, not code review:**
- **Anthropic opt-in path** — confirmed structurally identical to
  pre-migration (`provider="anthropic"` resolves to the exact original
  `claude-haiku-4-5-20251001`/`claude-sonnet-5` models, same request shape).
  A live round-trip currently fails with a real, expected
  `credit balance too low` error — the exact real-world condition driving
  this migration, not a defect in the migrated code.
- **single_image draft → critique → refine, 4 real topics** (`mindset-self-doubt`,
  `career-perfectionism`, `wellness-motivational`, and `mindset-attachment-styles`
  — the last one `requires_citation: true`, exercising #14/#15's knowledge_hints
  grounding path under the new models for the first time): all four ran
  end to end with substantive critiques (none empty, post-fix) and
  real refine changes. The citation-required trial's critique correctly ran
  a "fabricated_specifics_check" and found no fabricated study, date, quote,
  or unsafe statistic — #14/#15's grounding mechanism holds under the new
  model. The gendered-dimension requirement (`_brief_system_prompt`'s "must
  draw on why this topic specifically lands differently for a woman") was
  correctly flagged by critique and correctly fixed by refine in 2 of 4
  trials. Word limits held in all four (untolerant single_image cap,
  unaffected by this migration). No forbidden/banned phrases, no CTA/closing
  issues (structurally not applicable to single_image's one-slide shape).
  **One real, worth-tracking finding, not attributed to the model swap
  without evidence:** `career-perfectionism` (`stat_research` approach,
  `requires_citation: false`) drafted an unclear acronym ("FNE"), which
  critique correctly flagged as not delivering a real stat/finding — but
  refine's fix replaced it with an unhedged, non-specific claim ("Women face
  a tighter error margin") with no real number and no citation check
  available to catch it, since `requires_citation` is per-topic, not
  per-approach, and `stat_research` can be sampled for any topic including
  non-citation ones. This looks like a pre-existing architectural gap
  (any topic + `stat_research` + no citation requirement = no grounding
  check fires at all) rather than a new regression from the model change —
  no Claude-path comparison was possible to confirm either way, since
  Anthropic has no credits — but it's real and worth a follow-up look
  independent of this migration.
- **Full backend suite: 127/127 passing**, both before and after the
  `reasoning_effort` fix — no test changes needed, since every existing test
  monkeypatches `LLMProvider` at the route-module level rather than
  depending on its internals.
- **Real token usage, one full single_image generation** (angle + draft +
  critique + refine): cheap tier (`gpt-5.6-luna`) 308 input / 93 output
  tokens; strong tier (`gpt-5.5`) 3,776 input / 639 output tokens across the
  three strong-tier calls. Dollar cost deliberately not stated — no
  confirmed current per-token pricing for these specific models was
  available; see `docs/implementation-guide.md` Section 11 for the same
  numbers and the same caveat.

**`ENABLE_PROMPT_CACHE` re-examined, not assumed to carry over:** the flag's
original "~90% off cached input" description is Anthropic-specific
(`cache_control: {"type": "ephemeral"}`), still implemented unchanged in
`_complete_anthropic()`. The OpenAI path has no equivalent explicit
directive in this code — if `gpt-5.5`/`gpt-5.6-luna` cache repeated prompt
prefixes automatically on OpenAI's side, this codebase doesn't opt into or
control it, and no discount figure has been confirmed. Documented as
unmeasured in `docs/implementation-guide.md` Section 11 rather than assumed.

**Deviates from `CLAUDE.md`'s locked decisions — explicitly, not silently.**
The "Models" line (Section: Locked decisions) is updated to show the
reversal with a strikethrough, matching this project's existing practice for
deliberate locked-decision deviations (masthead simplification #32,
`voice_samples.direct` rewrite #30). Unlike those two, this one is fully
reversible with no redeploy (`LLM_PROVIDER=anthropic`), and was driven by a
hard external constraint (zero Anthropic credits) as well as evidence, not
evidence alone.

---

## 41. LIVE BUG, already shipping — `single_stat`'s `number` field had no word cap, and a real production refine step overflowed it catastrophically

**Symptom:** while scoping per-template word limits for a future carousel
port, a real `single_image` migration trial (`career-perfectionism`, logbook
#40) produced a refined `single_stat` slide with `number: "Women face a
tighter error margin"` — a 5-word, 34-character generalization sitting in a
field designed for a short numeral or stat like `"73%"`. Rendered through
the real, unmodified `/api/render` Satori pipeline, this filled the **entire
1080×1350 canvas with 5 lines of 200px text**, crowding out the kicker and
supporting_line entirely. Confirmed with a real render before touching any
code, not assumed from the JSON alone.

**Root cause:** `number` was never bounded by anything. The combined
`slide_text()` word check (`validator.py::_check_format`, pre-fix) summed
`kicker` + `number` + `supporting_line` against one flat 30-word cap — a
5-word `number` sitting next to a short `supporting_line` averaged out to a
combined count that looked completely unremarkable, so nothing could ever
have caught this via a whole-slide check. The field needed its own,
independent range.

**Fix:** `generator.py` gained `_SINGLE_STAT_NUMBER_WORD_RANGE = (1, 3)` and
`_SINGLE_STAT_SUPPORTING_LINE_WORD_RANGE = (15, 20)`, checked as two
separate fields in `validator.py::_check_single_stat_fields` — not folded
into the general per-slide word-range check other roles use
(`_WORD_RANGE_FOR_ROLE`). The system prompt and critique_post's per-slide
word guidance now state this explicitly for `single_stat`: *"number: 1-3
words, a short numeral/stat only, never a sentence (this field renders at
200px and overflows badly if long)."*

**Verified, real renders, both ends of the new range:** `number` at 1 word
(`"73%"`) and 3 words rendered cleanly, no overflow — the 3-word ceiling is
visually large but contained, not the canvas-filling failure the uncapped
field produced. `supporting_line` at 15 and 20 words both rendered cleanly.
Regression tests added (`test_validate_post_flags_single_stat_number_field_overflow`
reproduces the exact real failure — 6-word `number` — and asserts it's now
caught; `test_validate_post_passes_single_stat_with_short_number_field`
confirms the correct shape still passes clean). Full backend suite:
**132/132 passing.**

**Not a blueprint deviation** — this is a bug fix (a field with no bound
that should always have had one), not a design change. Directly relevant to
the still-open carousel-port scoping this was found during, but real and
worth fixing on its own regardless of whether that port ever ships — this
overflow could happen on any live `single_image`/`stat_research` generation
today.

---

## 42. LIVE BUG, already shipping — `SingleQuote.tsx` had no vertical centering, leaving short quotes with large empty space at the bottom of the slide

**Symptom:** found via the same per-template word-limit investigation as
#41 — a real render of a real single_image migration output (a 22-word
quote) filled only the top ~45% of the canvas, with the entire bottom half
left empty. Every other slide template in this codebase
(`CarouselBody`/`CarouselBodyTeaching`/`CarouselClosing`/`ConversationSlide`/
`SingleStat`) wraps its content in a `flex: 1, justifyContent: "center"`
container; `SingleQuote.tsx` was the one exception — a fixed `marginTop: 56`
top-anchor with no centering and nothing below to fill the remaining space
(unlike `CarouselCover`, whose hero image fills the bottom regardless of
headline length).

**Fix:** wrapped `SingleQuote`'s content in `flex: 1, justifyContent:
"center"`, matching the other five templates' convention. Also reduced the
quote text's `marginTop` from `240` (a spacing hack sized for the old
top-anchored layout, positioning the text partway down behind the
decorative giant quote-mark glyph) to `48`.

**A real, unexpected finding while verifying this fix — reported honestly,
not glossed over:** re-rendering at multiple word counts (1 word through 40
words) showed the text block's vertical position does **not** change with
content length at all — a control test on the already-working
`carousel_closing` template (1-word vs. 20-word takeaway) showed the exact
same behavior. This means Satori's `justify-content: center` does not
dynamically recompute the centered position as content grows the way full
browser CSS would — every flex-centered template in this codebase,
including the five that were already considered "working," anchors near a
fixed point rather than truly centering dynamically. This is a Satori
CSS-subset limitation (`docs/implementation-guide.md`'s render section
already documents Satori as a constrained subset, not full CSS), not a
defect introduced by this fix. The practical result for `SingleQuote` is
still a real, verified improvement — the anchor point moved from
just-below-the-masthead (near the very top of the canvas) to the same
mid-canvas point every other template already uses, which is a
meaningfully better default position even without dynamic growth — but it
is not a claim that quotes of any length now center "perfectly." Flagged
here as a known, shared engine limitation rather than reopening this as an
unresolved bug.

**Verified, real renders:** short (10-word) and long (28-40 word) quotes
both rendered at the corrected mid-canvas anchor point, confirmed against a
direct before/after comparison with the original top-anchored render. No
backend change, no test changes (this is frontend-only, not covered by the
backend suite) — full backend suite still **132/132 passing**, confirming
this fix didn't touch anything backend-adjacent.

**Not a blueprint deviation** — a bug fix (a missing convention every
sibling template already follows), not a design change.

---

## 43. OPEN, EXPERIMENTAL — carousel direct-write port: single-call writer replacing draft→critique→refine, carousel only

**What this is:** the production carousel writer's biggest structural change
since the v1 checklist experiment (#39) — not another prompt patch on top of
`draft_post → critique_post → refine_post`, but a full replacement of that
loop for carousel with the single-call, free-anchor-pick design validated
across this session's POC testing (`docs/direct-write-poc.md`) and the port
test harness investigated in #40. `single_image` is completely untouched —
`draft_post`/`critique_post`/`refine_post`/`generate_post` still exist,
unmodified, and are exactly what `single_image` still calls.

**`angle_engine.py`: `assemble_carousel_context()`, pure Python, no LLM
call.** Replaces `sample_cell()`/`generate_angle()` for this path — pulls
`topic.primary_category`, all of `topic.seed_angles` (not one sampled
sub-concept), `topic.knowledge_hints` when `requires_citation`, and this
topic's own recorded anchors from memory (the avoid-list). Confirmed by
reading the function: it never calls `sample_cell`/`generate_angle`, and
never reads `approach` or `entry_point` — both concepts don't exist on this
path at all, and stay used only by `single_image`'s unchanged one.

**`memory` table: new `anchor` column**, same additive pattern as
`caption`/`slides`/`exported_at` (#35) and `anchor`'s own introduction to
`MemoryRecord` and `schema.sql` in this same round of work — a
`create table if not exists`-block addition plus an explicit
`alter table memory add column if not exists`, since the block alone is a
no-op against the already-live production table (a gap this file has always
had for post-launch columns, made explicit here rather than left implicit).
Empty for every pre-existing record and for `single_image`.

**`generator.py`: `draft_carousel_direct()`, one strong-tier call.** No
provider wiring needed — inherits the `gpt-5.5` default from the completed
migration (#40). Implements POC rules 1-12 (rule 13, selective line breaks,
dropped — it existed for the POC's own freeform-paragraph slide template,
which has no equivalent in production's typed slide fields), category +
seed_angles as context the model can freely use or ignore (not a dictated
cell), knowledge_hints-conditional grounding via the *same*
`_citation_mode()` dispatcher `single_image` still uses (factored the
citation instruction text into a new shared `_citation_instruction_block()`
so the two paths can't drift on wording), the anchor avoid-list, and mood
folded into the same JSON call rather than a separate cheap-tier tagging
call. Voice register hardcoded to `"poetic"` — not resolved via
`APPROACH_REGISTER`, since there is no sampled approach on this path to
resolve it from.

**The `approach` field is real plumbing, not a real signal — flagged
explicitly, not left implicit.** `ContentBrief.approach` is a required field
with no default, and `slide_roles_for()` and `validate_post()` both key off
it. The caller sets it to `Approach.QUESTION_REFLECTION` for every post on
this path — chosen specifically because it's the one
`CAROUSEL_V1_APPROACHES` member *not* in `TEACHING_BODY_APPROACHES`, so
`slide_roles_for()` already resolves to plain `carousel_body` (never
`carousel_body_teaching`) with zero changes to that function, and already
resolves to `"poetic"` via `APPROACH_REGISTER` if anything downstream reads
it that way. `draft_carousel_direct()` itself never reads `brief.approach`
for anything.

**A real sequencing decision, also flagged rather than glossed over:**
`mood` is decided by the same single call that writes the content, but
`build_brief()` needs `mood` (and `angle`) as *inputs*. There's no way to
sample them first the way `generate_angle()` used to. The resolution:
callers build a **provisional** brief first (`angle`/`mood` as clearly
labeled placeholders — only `requires_citation`/`sources`/`knowledge_hints`/
`format` are real and used, for the citation instruction), call
`draft_carousel_direct()`, then correct `brief.angle`/`brief.mood` from its
returned `(post, anchor, mood)` before passing the brief to `validate_post`
or writing a `MemoryRecord`. `fingerprint` for the repetition check is
`f"{topic_id}:{anchor}"` — the natural analog of the old
`topic_id:sub_concept:approach` fingerprint now that anchor, not sub-concept,
is the thing that shouldn't repeat. This function-level engine work is in
scope here; wiring it into `routes/generate.py` end-to-end (including hero
image sequencing) is explicitly not — that's the next piece, not done yet.

**Body slides: a real adaptation, not a literal POC port.** The POC's own
slides are full paragraphs; production's `carousel_body` is a short
statement (`statement_pre`/`statement_script`/`statement_post`, one
emphasized phrase). Reworking POC's "reword, don't copy" rule for this
shape wouldn't have made sense — instead, a new instruction asks the model
to select 3 of the caption's real beats and *compress* each into a punchy
statement (a compression, not a retelling), reusing
`_WORD_RANGE_FOR_ROLE["carousel_body"]` (#41/#42's work) for the target,
not a new number. `headline_word`/`script_word`/`kicker` (cover) and
`closing_takeaway` are asked for as explicit, separately-named JSON fields
the model writes deliberately — same pattern `conversation_question`
already used — not derived by parsing the caption after the fact.

**No `critique_post`/`refine_post` call on this path — the reasoning is in
the code, not just here, and the small sample size is stated explicitly,
not implied.** This mirrors what `docs/direct-write-poc.md` Section 5 found
(direct-write beat eight rounds of patching the checklist-based prompt this
replaces) and what this session's port test harness (#40's investigation)
found in real trials: the single-call design held up cleanly against the
specific failure modes the critique/refine backstops exist to catch
(closing-declarative drift, reader-address leaking into a body slide). That
evidence is real but from a handful of trials across a handful of topics —
nowhere near the volume the checklist writer's own backstops were hardened
against over #39's many rounds. If real output review at scale finds these
failure modes returning, adding a narrow critique pass back for this path
specifically (not the full three-call loop) is the documented next step.

**`validator.py`: confirmed unchanged, not assumed.** Full backend suite
stayed **132/132 passing** throughout this work, without touching
`validator.py` at all — direct confirmation, not just the design reasoning
above (the `QUESTION_REFLECTION` approach choice routing through
`slide_roles_for()` unmodified) that no changes were needed there.

**Verification, real API calls and real Satori renders throughout:**
- **Category disambiguation, a fresh collision set (Burnout, not
  Boundaries):** `career-burnout` and `wellness-burnout` — different
  categories, same topic name — independently converged on the same anchor
  ("canary in a coal mine"), a real instance of the already-documented
  anchor-convergence gap (`FINDINGS.md` #1). Despite the shared anchor, the
  actual content stayed clearly domain-differentiated: career-burnout's
  piece is explicitly workplace-framed ("the reliable woman keeps getting
  more work"), wellness-burnout's is explicitly somatic ("a weekend of
  sleep does not bring her back"). `relationships-burnout` landed on a
  genuinely different anchor ("day hospital nursery") with clearly
  relationship-specific content. Same pattern as the earlier Boundaries
  finding: category+seed_angles context fixes domain-blindness; it does not
  fix anchor-level convergence, a distinct, still-open problem.
- **Anchor avoid-list, a real before/after pair:** `mindset-boundaries` with
  no avoid-list produced anchor *"Hedy Lamarr's frequency hopping"*; the
  same topic, re-run with that anchor in a real `MemoryRecord`-backed
  avoid-list, produced *"Victorian calling cards"* — confirmed different,
  and confirmed the avoid-list text was actually present in the context
  handed to the model, not just assumed to have worked because the anchor
  changed.
- **knowledge_hints grounding, 3 more citation topics beyond Attachment
  Styles:** `career-pay-scale`, `wellness-stress-regulation`,
  `health-hormonal-cycle` — all three stayed properly hedged, no fabricated
  studies/statistics/dates, real anchors (mad money; the mammalian diving
  reflex; a basal body temperature chart) matching each topic's
  `knowledge_hints`.
- **Word ranges on real output:** 5 of 6 verification posts passed clean;
  one (`wellness-stress-regulation`) was **correctly flagged** — a body
  distillation came in at 7 words, genuinely below the template's floor.
  Reported as the floor doing its job, not a bug — the exact class of
  problem #41/#42's per-template ranges exist to catch, now confirmed
  catching a real case from this new writer's own real output, not just a
  synthetic test fixture.
- **Real Satori renders, cover/closing/one body slide, not just JSON:** all
  six cover/closing renders read cleanly — on-brand kickers passing
  `_KICKER_INSTRUCTION`'s "real sentence, not a label" bar, closing takeaways
  100% declarative (zero question-drift across 8 real closing lines
  checked), no overflow, no sparse-looking slides. One body slide rendered
  confirms the compression instruction is producing real, punchy
  distillations (*"The bird was not weak. / The air had become
  dangerous."*), not reworded paragraphs.
- **Full backend suite: 132/132 passing**, unchanged from before this work
  started.

**Not yet done, explicitly:** wiring this into `routes/generate.py` (hero
image sequencing in particular needs real thought, since `visual_subject`
no longer comes from a separate cheap-tier call the way it does for
`single_image`); a real decision on whether/how to close the anchor-
convergence gap found again in the Burnout test; any critique-pass addition,
per the "small sample size" caveat above. This entry documents the writer
itself, verified in isolation — not a claim that the full carousel pipeline
has been replaced end-to-end.

**Not a blueprint deviation in the usual sense** — this is the continuation
of #39's already-logged, already-experimental carousel-only line of work,
now at its most structural point yet (a full writer replacement, not a
prompt patch). Still explicitly open and experimental, same as #39 was
throughout its eight rounds.

---

## 44. OPEN, EXPERIMENTAL — carousel direct-write port's body slides routed to `carousel_body_teaching` for more room

**Trigger:** a direct follow-up investigation (logged separately) confirmed
`carousel_body_teaching` was not dead code — the old, still-live carousel
path (`sample_cell` → `generate_angle` → `generate_post`) reaches it
whenever `STORY` gets sampled from `CAROUSEL_V1_APPROACHES`, since `STORY`
is the one member that set also shares with `TEACHING_BODY_APPROACHES`.
Given the template was already real and reachable, and #43's `carousel_body`
routing gave the body slots a cramped 10-20 word range, this round moves
#43's writer onto the roomier template instead.

**What changed, `generator.py`:**
- `_parse_carousel_direct_response()`'s body slots now build `BodyTeachingSlide`s
  (`heading`/`body` fields) instead of `BodySlide`s (`statement_pre`/`script`/
  `post`) — role list changed to `carousel_body_teaching` × 3.
- New schema fields: `body_N_heading` (a short phrase, a few words) alongside
  `body_N_text`. Explicitly instructed as **not** a real teaching-style label
  and **not** a restatement of the body text — just enough to give the slide
  a lead-in, matching what the template structurally needs without asking the
  model to actually "teach."
- The body-slot instruction changed from "compress into a punchy statement"
  to "retell fresh, same moment/image/idea, different sentence, never
  verbatim" — the isolated POC's own already-validated slide-instruction
  pattern (`docs/direct-write-poc.md` Section 11), which fits this template's
  35-50 word range far better than the "cut to the sharpest line" compression
  instruction #43 needed for `carousel_body`'s much smaller range.
- Word target switched to `_WORD_RANGE_FOR_ROLE["carousel_body_teaching"]`
  (35-50, tolerant 31-55) — still reused directly, no new numbers invented.

**A real dependency this surfaced, fixed in the same pass:** `validator.py`'s
`_check_format` calls `slide_roles_for(brief)` independently to know which
range to check each slide against — it does not read what role the writer
itself actually produced. #43's brief hardcoded `approach=QUESTION_REFLECTION`
specifically so `slide_roles_for` would resolve to `carousel_body` (matching
what #43's writer produced then). Simply changing the writer's output to
`carousel_body_teaching` without also changing this would have silently
desynced the two — `validate_post` would have checked real 35-50 word
content against `carousel_body`'s 9-22 word tolerant ceiling, flagging every
single post as wildly over-length. Fixed by changing the caller's hardcoded
approach to `Approach.STORY` instead — the sole approach both sets share, so
`slide_roles_for` now resolves to `carousel_body_teaching` and stays in
agreement with the writer's actual output, still with zero changes to
`slide_roles_for`/`validator.py` themselves. Caught before shipping, not
after — worth calling out explicitly since it's exactly the kind of
cross-file dependency that's easy to miss when one file (the writer's
parsing) is edited without tracing who else depends on the same brief field.

**Verified, real API calls, 4 fresh topics (`mindset-perfectionism`,
`career-imposter-syndrome`, `relationships-people-pleasing`,
`wellness-rest`) not reused from #43:**
- **No overflow anywhere** — confirmed across all 4 topics, 12 body slides.
- **A real, honest finding, not glossed over:** 2 of 4 topics tripped the new
  31-word tolerant floor — `career-imposter-syndrome` by one word (30 vs
  31), `wellness-rest` more substantially (29, 26, 28 words across all three
  of its body slides). Real Satori renders of both a passing example (40
  words: 3 full sentences, reads as intentional) and a flagged example (26
  words: 2 shorter sentences) confirm the floor is catching a real visual
  difference, not a false positive — the flagged render is noticeably
  thinner, not just numerically short. Not fixed in this round; noted as a
  real, mild undershoot tendency worth watching in future rounds, the same
  way rule 1's early-signal instruction needed a hardening pass before it
  held reliably.
- **Headings read as intentional, not filler**, across all 12: *"The bright
  repair," "The polished room," "What holds"* (mindset-perfectionism);
  *"A voice in the room," "When credit moves," "The careful caveat"*
  (career-imposter-syndrome); *"The hidden bill," "The polite reflex,"
  "The quiet exit"* (relationships-people-pleasing); *"Two fingers," "After
  everything," "The quiet report"* (wellness-rest). Each is a real, specific,
  evocative mini-title tied to its own beat's image — none read as a generic
  placeholder or a restatement of the body text beneath it.
- **Real Satori renders, cover/body/closing**, not just JSON: all read
  cleanly, no overflow, on-brand kickers, declarative closings echoing each
  anchor.
- **Full backend suite: 132/132 passing**, unchanged.

**Not yet done:** the word-floor undershoot tendency found here is real and
unaddressed — a candidate next step if this line of work continues, same
"documented, not a surprise" framing as #43's own critique/refine caveat.

**Addendum — narrative-fidelity check, closing the loop on whether the
retelling actually holds up, not just the word count (same session):** a
direct concern with this whole line of work is whether pulling 3 of the
caption's beats out into their own slides reproduces the isolated POC's
first failed "reshape" attempt (`docs/direct-write-poc.md` Section 11) —
where 1 of 3 trials collapsed into copying the caption verbatim rather than
genuinely retelling it. Checked directly: **5 fresh real topics**
(`mindset-self-doubt`, `career-office-politics`, `wellness-sleep`,
`relationships-invisible-labor`, `society-quirky-fun`), each caption split
into its real beats and matched by hand against its 3 body slides.

Result: **no full-sentence verbatim reuse in any of the 15 slides checked**
— a categorically better result than the POC's first attempt, which had
verbatim copying in 1 of 3. Every slide retained its source beat's concrete
image and point (e.g. `mindset-self-doubt`'s ducking-stool scene survives
intact into "The public chair," reworded, not copied; `society-quirky-fun`'s
closing slide invents a fresh pun — "dress itself up" — tied to the anchor
that never appeared in the caption at all). One minor near-verbatim
instance flagged, not glossed over: `wellness-sleep`'s third slide's "the
hour gets slower" sits close to the caption's own "a slower hour" — a
three-word overlap, not a sentence-level copy, but worth naming.

The compression shape was also consistent trial to trial, not
topic-dependent: every one of the 5 trials implicitly followed the same
3-act structure — slide 1 draws on the anchor's own opening scene (beats
1-2), slide 2 draws on the modern-life translation (beats 3-5), slide 3
draws on the closing turn (beats 6-7) — usually compressing 2 adjacent
caption beats into one slide rather than a strict 1-beat-per-slide mapping.
This narrative-fidelity question is now closed for this round of testing;
it does not need to be re-litigated blind next time this path is picked up.

**Not a blueprint deviation** — continuation of #39/#43's already-logged,
already-experimental carousel-only line of work.

---

## 45. OPEN, EXPERIMENTAL — carousel direct-write port gains a real hero image (`visual_subject`), reusing the existing prompt-styling logic

**What changed, `generator.py`:** `draft_carousel_direct()`'s single call now
also asks for `visual_subject` — 5-15 words naming one concrete,
photographable image tied to the anchor, same zero-extra-cost pattern as
`mood`/the cover fields/`conversation_question` (one more field in the same
JSON, not a second call). The instruction text is adapted from
`generate_angle()`'s own already-proven `visual_subject` guidance
(`angle_engine.py`) — same "a photographer could actually go photograph,
never an abstract mood word, never a stock-photo trope" bar, reworded to
reference the anchor this path has instead of the topic+angle pair
`generate_angle()` had. `_parse_carousel_direct_response()` falls back to
the anchor itself if the model omits it, same fallback shape
`_parse_angle_response`'s `fallback_visual_subject` already uses.
`draft_carousel_direct()` now returns `(post, anchor, mood,
visual_subject)`.

**Checked before writing anything, per the actual ask — reused, not
rebuilt:** `brief_builder._hero_image_prompt(subject, mood)` already exists
(`f"Abstract, editorial, textural image of {subject}, no literal faces or
text, {mood} mood."`) and is already imported and reused as-is by
`sources/paste_link.py` for its own visual_subject. No new styling logic
was written — this path's caller wraps its raw `visual_subject` through
that exact same function before calling the real image pipeline, the same
way `build_brief()` already does for `generate_angle()`'s output.

**Verified, real API calls, real image pipeline, 4 fresh topics
(`mindset-rest`, `career-perfectionism`, `relationships-burnout`,
`health-reproductive-health`):** ran `draft_carousel_direct()`, wrapped the
real `visual_subject` through the real, unmodified `_hero_image_prompt()`,
called the real `ImageProvider` (GPT Image 2) and the real
`duotone_and_cache()` — not mocked, not just a string check. Four real
hero images produced and read directly, not assumed from a prompt string:
a screened sleeping porch with a white iron bed; a kintsugi-repaired
ceramic bowl; a kitchen table with folded laundry and papers; a folded
paper exam gown on an exam table. All four read as genuinely on-brand —
abstract, editorial, textural, zero literal faces or people (so no uncanny-
face risk at all, since the visual_subject instruction steers toward
objects/scenes rather than people), each specifically tied to its own
anchor rather than a generic or swappable image. The citation-required
topic (`health-reproductive-health`) produced a tasteful, non-clinical-
feeling image despite the sensitive subject matter.

**Full backend suite: 132/132 passing.**

**Not a blueprint deviation** — continuation of #39/#43/#44's already-
logged, already-experimental carousel-only line of work; reuses an existing
function rather than introducing a new design decision.

---

## 46. OPEN, EXPERIMENTAL — carousel direct-write port wired into `routes/generate.py` as the real path, `CAROUSEL_WRITER=direct_write` default

**What changed:** `run_generate()` now branches for a fresh (non-preselected)
carousel request: `CAROUSEL_WRITER=direct_write` (the new default) routes to
a new `_generate_carousel_direct()`, replacing `sample_cell` →
`generate_angle` → `build_brief` → `generate_post` for that call.
`CAROUSEL_WRITER=legacy` is the opt-in fallback to the exact original chain,
same escape-hatch pattern as `LLM_PROVIDER` — not a hard cutover. (Renamed
from an original `v1` value in logbook #47 — `docs/direct-write-poc.md`
locks "v1"/"v2" to mean only the hand-written reference pieces, never a
pipeline; this flag's old chain is "legacy", not "v1", full stop.)
`single_image` never reaches this branch at all and is completely
unaffected. `_generate_for_brief`'s validate/memory-write/response tail was
factored into a shared `_finalize_generation()` helper so both chains build
their `GenerateResponse`/`MemoryRecord` the same way — `anchor` (empty for
every other path) now gets populated from the writer's real output for
carousel direct-write, not left blank.

**Explicit check done, not assumed, per the actual ask: does
`engine/selector.py`'s coverage/diversity weighting read `approach` from
memory records?** No. Read `_topic_weight()` and `select_daily_picks()`
directly: coverage weighting only counts `MemoryRecord.topic_id`
occurrences, and category-variety enforcement only reads
`topic.primary_category` — neither touches `approach` anywhere. Confirmed
by grep (`grep -n "\.approach\b" selector.py`): the only two hits are
storing a *freshly sampled* `sampled.approach` on a new `DailyPick`, never
reading it back from historical memory. So hardcoding `approach=STORY` as
pure plumbing for every direct-write carousel post cannot break this
specific signal — it was never approach-aware to begin with.

**A related, real, distinct finding surfaced along the way, reported
either way per the ask:** `build_daily_pick()` still calls the unmodified
`generate_angle()`/`sample_cell()` for its own hook/thumbnail preview,
which *does* do approach-aware fingerprint exclusion (`topic:sub_concept:
approach`) — entirely separate machinery, unaffected by this wiring, since
daily-picks previews never call `draft_carousel_direct` regardless of
`CAROUSEL_WRITER`. But direct-write's own memory records carry a
differently-shaped fingerprint (`topic_id:anchor`), so they're invisible to
`sample_cell()`'s own exclusion set — a real, orthogonal consequence:
direct-write's generation history doesn't feed back into `single_image`'s
or legacy-carousel's non-repetition check on the same topic, and vice versa.
Not fixed here, not blueprint-relevant to fix silently — flagged for
whoever picks up cross-path non-repetition next.

**A real, honest architectural tradeoff, not glossed over:** the legacy
chain's cheap-tier `generate_angle()` call already knows mood/visual_subject
*before* the strong-tier draft starts, so its hero image generation runs in
parallel with the text (`asyncio.gather`). Direct-write's mood/
visual_subject aren't known until the single writer call returns, so hero
generation must run sequentially after it. A direct-write carousel
generation is slower end-to-end than legacy, not faster — a real cost of
this design, not a regression introduced by wiring it in.

**Preselected angles always bypass direct-write, on purpose.** A
`preselected` `SampledAngle` means the client already saw and accepted a
real `sample_cell`-driven proposal (`/generate/propose`, or a daily pick's
precomputed hook/thumbnail) — direct-write has no equivalent to preview
first, one call decides everything at once. `run_generate()` checks
`preselected is None` before routing to direct-write, so any preselected
carousel request — including every daily-pick tap, since picks are built
via `generate_angle` — still uses the legacy chain today regardless of
`CAROUSEL_WRITER`. This is a real, deliberate scope boundary of this wiring
pass, not an oversight; whether daily-pick taps should also eventually use
direct-write is a separate, undecided product question.

**Verified, real API calls, real end-to-end `/generate`-shaped calls
against real Supabase — not each piece in isolation:**
- **Non-citation topic** (`mindset-perfectionism`): anchor *"sampler girls'
  stitched mistakes"*, mood `wisdom`, hero image generated (real GPT Image
  2 + duotone, viewed directly — abstract, editorial, no faces), validation
  passed clean, real `MemoryRecord` written to Supabase and **read back
  in a fresh query** with the correct anchor intact — confirms the anchor
  column (logbook #43, applied live in a separate migration step) actually
  round-trips through the real database, not just exists as a column.
- **Citation-required topic** (`wellness-stress-regulation`): anchor
  *"mammalian diving reflex"*, same full chain, same clean result,
  read-back confirmed.
- **Daily-picks/selector confirmed to behave sanely afterward**, against
  real current memory (145 records, including the two direct-write records
  just written): `select_daily_picks()` still returns 3 picks with correct
  category variety, `_topic_weight()` computes normally for a topic that
  now has direct-write-shaped records in its history. Existing
  `test_selector.py`/`test_picks_route.py` suites (16 tests) pass
  unchanged, since `selector.py` itself was never touched.
- **Full backend suite: 135/135 passing** (132 plus 3 new tests: direct_write
  is confirmed the real default, the `legacy` override is confirmed to
  actually route there rather than just existing as a setting, and a
  preselected angle is confirmed to bypass direct-write). Two pre-existing
  carousel tests were re-pinned to `carousel_writer="legacy"` since they
  specifically exercise that chain's fixtures, not renamed away — they
  still cover exactly what they always did. (Both the flag value and these
  tests were originally named `v1`/`carousel_writer="v1"` — renamed to
  `legacy` in logbook #47 to remove the collision with
  `docs/direct-write-poc.md`'s locked "v1"/"v2" terminology.)

**Not a blueprint deviation in the usual sense** — continuation of
#39/#43-45's already-logged, already-experimental carousel-only line of
work, now live-reachable via the real `/generate` route (gated, reversible,
not a hard cutover) rather than only verified in isolated scripts.

---

## 47. Renamed `CAROUSEL_WRITER`'s fallback value from `v1` to `legacy` — a real terminology collision, not cosmetic

**Symptom:** `docs/direct-write-poc.md` Section 1 locks "v1"/"v2" to mean
*only* the four/six hand-written writing-style reference pieces (Shimenawa,
Shmita, mad money, amae) — explicitly, permanently never a pipeline or code
path, and explicitly calling out that logbook #39's own original "carousel-
only 'v1'" self-labeling is superseded by that lock. #46's
`CAROUSEL_WRITER=v1` flag value (added the same session, after that lock
was already written) directly re-created the exact collision that document
exists to prevent — a second instance of the same mistake #39 made first.

**Fix:** renamed the flag's fallback value from `"v1"` to `"legacy"`
everywhere: `config.py` (default/comment), `routes/generate.py` (every
comment/docstring reference to "the v1 chain"), `.env`/`.env.example`,
and `tests/test_generate_route.py` (both the `carousel_writer="v1"` setting
overrides and the test function names/docstrings that referenced it —
`test_run_generate_carousel_v1_returns_hero_and_writes_memory` →
`..._legacy_...`, etc.). `routes/generate.py` never hardcoded the literal
string `"v1"` in any comparison (only `== "direct_write"`, treating
anything else as fallback), so the rename touched no runtime branching
logic, only strings, comments, and test fixtures.

**Terminology note added in three places, not just the rename itself:**
1. `config.py`, directly beside the flag's own definition — an explicit
   "if you're about to type 'v1' to describe a pipeline or code path
   anywhere in this codebase, stop" comment.
2. `docs/direct-write-poc.md` Section 1 — two new rows added to the locked
   terminology table (**the carousel direct-write port**; **legacy**, as in
   `CAROUSEL_WRITER=legacy`), plus a new explicit paragraph naming both
   times this exact collision has now happened (logbook #39's original
   self-labeling, and this flag) and stating the rule plainly for next
   time: every pipeline/code path gets a real name, never a version-number
   shorthand.
3. `CLAUDE.md`'s carousel-port status paragraph, inline at the point the
   flag is introduced.

**Verified:** full backend suite still **135/135 passing** after the
rename — confirms the rename touched no runtime branching logic, only
strings/comments/test names, exactly as expected from reading
`routes/generate.py`'s actual comparison logic first rather than assuming.

**Explicitly out of scope, flagged rather than silently left alone:**
logbook #39's own historical "carousel-only 'v1' content-voice experiment"
phrasing (used throughout #39's own entries, predating
`docs/direct-write-poc.md`'s lock) and the unrelated `CAROUSEL_V1_APPROACHES`
Python constant (`taxonomy/approaches.py`) are a second, older, larger
instance of the same underlying collision — not touched here. This task
was scoped specifically to the `CAROUSEL_WRITER` flag; renaming `logbook
#39`'s own historical entries or a real, already-shipped Python identifier
used throughout `angle_engine.py`/`generator.py` would be a separate,
larger, riskier change than what was asked, not a natural extension of it.

**Not a blueprint deviation** — a terminology/naming fix, not a design
change.

---

## 48. `/picks` 500ing in production — Railway's `LLM_MODEL_CHEAP`/`LLM_MODEL_STRONG` were still pinned to pre-migration Claude model strings

**Symptom:** reported urgent — daily picks (`GET /picks`) failing live in
production, apparently "calling Anthropic despite the provider migration."

**Investigation:** reproduced directly rather than reading code and
guessing. Local repro (`.env`'s real `LLM_MODEL_CHEAP=gpt-5.6-luna`/
`LLM_MODEL_STRONG=gpt-5.5`) worked cleanly end-to-end — `GET /picks`
returned a real, freshly-computed `DailyPicksResult`, confirming
`get_or_compute_daily_picks`/`generate_angle`/`LLMProvider` all work
correctly as written. Checked every `LLMProvider(...)` call site in
`app/routes/*.py` for an explicit `provider="anthropic"` override that
the migration might have missed — none exist; `/picks` (`routes/picks.py`)
constructs `LLMProvider()` plain, same as every other route.

`railway variables` (real production values, not assumed) showed the
actual mismatch: `LLM_PROVIDER` was never set on Railway at all — harmless,
since `config.py`'s default is already `"openai"` — but `LLM_MODEL_CHEAP`
and `LLM_MODEL_STRONG` were still set as explicit Railway service
variables to their pre-migration values, `claude-haiku-4-5-20251001` and
`claude-sonnet-5`. Railway variables override `Settings`' Python-level
defaults, so these two leftover variables silently kept shadowing
`config.py`'s new `gpt-5.6-luna`/`gpt-5.5` defaults ever since the
migration shipped (`docs/logbook.md` migration entry) — the model-name
variables were never part of that migration's own checklist.

Reproduced the exact production failure locally (real env-var match:
`LLM_PROVIDER` unset, `LLM_MODEL_CHEAP`/`LLM_MODEL_STRONG` set to the
Claude strings) and got the identical crash, real traceback, not a guess:

```
openai.NotFoundError: Error code: 404 - {'error': {'message': 'The model
`claude-haiku-4-5-20251001` does not exist or you do not have access to
it.', 'type': 'invalid_request_error', 'param': None, 'code':
'model_not_found'}}
```

The provider-selection half of the migration (`LLMProvider` defaulting to
`"openai"`) was genuinely live and working correctly in production — the
request really did go to OpenAI's API, using the real OpenAI client and
key. It just carried a Claude model name into that request, because the
model-name variables were a separate, unmigrated piece of config. Not an
Anthropic-path bug, and not a missed code path — a stale ops/env-config
gap the code-level migration never touched.

**Fix:** `railway variable set LLM_MODEL_CHEAP=gpt-5.6-luna --service
wgs-backend` and `railway variable set LLM_MODEL_STRONG=gpt-5.5 --service
wgs-backend`. Each `variable set` call triggers Railway's normal
auto-redeploy (not a manual `railway up`); confirmed the deploy completed
(`railway status` returning to plain `Online`, no `Building`/`Deploying`)
before considering this done.

**Verified live, not just deployed:** `curl
https://wgs-backend-production.up.railway.app/picks` after the redeploy
returned real HTTP 200 with a freshly-computed `DailyPicksResult` (real
topic/angle/hook/thumbnail content, not cached leftovers from the broken
state) — confirms the fix is live in production, not just committed
config.

**Not a blueprint/implementation-guide deviation** — an environment
configuration drift bug (two Railway variables left stale after a model
migration), not a design decision. Worth noting as a process gap for any
future model migration: updating `config.py`'s defaults is not sufficient
by itself if a target platform has the old values pinned as explicit
environment variables — those need an explicit audit/update step too, not
just an assumption that removing/changing a Python default takes effect
everywhere.

---

## 49. Correction — direct-write is not reachable from any current frontend flow, not just daily-pick taps

**Symptom:** none in production; caught by directly tracing the real
tap-to-generate flow rather than reading `#46`'s own claim at face value.
`#46`/`CLAUDE.md` had asserted "a preselected angle (from
`/generate/propose`, or any daily-pick tap, since picks are built via
`generate_angle`) always still uses legacy" — worded as if a daily pick's
own precomputed hook/angle were the thing becoming `preselected`.

**Investigation:** traced the actual frontend code, not assumed.
`frontend/app/page.tsx`'s `goToGenerate(topicId)` is the `onCreate`
handler for both a daily-pick card tap (`TodaysPick`/`PickCard`) and a
plain category-browse tap — identical function, no distinction between
entry points. It only carries `topic_id` via a query param; the daily
pick's own precomputed `angle`/`approach`/`mood`/`hook` (`DailyPick`,
`selector.py`) is discarded entirely, never reaching `/generate`.
`GenerateScreen` (`frontend/app/generate/page.tsx`) then unconditionally
calls `POST /generate/propose` on mount (`loadProposal`, a fresh
`generate_angle()` sample, independent of the daily pick) before any
"Generate" tap is even possible — the button that calls `generatePost()`
only renders once a proposal exists, and `handleGenerate` always passes
that proposal's `angle`/`approach`/`mood`/`visual_subject`/`fingerprint`
as the preselected fields. `generatePost`'s `accepted` parameter is
optional in `lib/api.ts`, but has exactly one call site in the whole
frontend (`generate/page.tsx:74`), and that call site always supplies it.

Net effect: every carousel `/generate` call the current UI can ever
produce arrives with all five preselected fields set — `preselected` is
never `None` on the live frontend, for any entry point. Direct-write's
`preselected is None` gate (`routes/generate.py::run_generate`) is
correct and doing exactly what it's supposed to do; the gap is that
nothing in the current UI can ever satisfy it, not something specific to
daily picks.

**Fix:** corrected `CLAUDE.md`'s wording to state this precisely — the
daily pick's own precomputed angle/hook is discarded rather than
preselected, and the real reason legacy is forced is that `GenerateScreen`
always routes through `/generate/propose` first, for every entry point.
Also named the practical consequence explicitly: direct-write cannot run
outside of tests today without a UI path that calls `/generate` without a
preselected angle — not merely a hypothetical, a real prerequisite for
this port to ever be exercised live.

**Verified:** confirmed by direct code trace (`page.tsx`, `generate/page.tsx`,
`api.ts`), not inference — `generatePost`'s single call site and its
always-populated `accepted` argument were read directly, not assumed from
the function signature alone.

**Not a blueprint deviation** — a documentation-accuracy correction about
an existing, already-shipped scope boundary (logbook #46), not a new
design decision or code change. No code was touched.

---

## 50. Carousel skips the propose/preview step so a real UI tap can actually reach direct-write

**Symptom:** logbook #49 established that direct-write (logbook #43-46)
was unreachable from any live frontend flow — every carousel `/generate`
call the UI could produce always carried a preselected angle (from a
`/generate/propose` roll), which forces `run_generate` down the legacy
chain regardless of `CAROUSEL_WRITER`. Direct-write existed, was wired in,
and was fully tested against the backend directly, but had never actually
been exercised by a real tap through the app.

**Fix:** `frontend/app/generate/page.tsx`, carousel-only — `single_image`
is completely untouched.
- `GenerateScreen`'s effect no longer calls `loadProposal()`/
  `proposeApproach()` when `format === "carousel"`; it just clears any
  leftover `proposal` state. `single_image` still calls it exactly as
  before, on the same `[topicId, format, singleImageStyle]` dependencies.
- Carousel's `handleGenerate` calls `generatePost(topicId, "carousel")`
  with the `accepted` argument omitted entirely, so the `POST /generate`
  body carries no `angle`/`approach`/`mood`/`visual_subject`/`fingerprint`
  — `preselected` is genuinely `None` on the backend, the same shape a
  fresh (non-preselected) call already needed.
- Since carousel no longer has a proposal to read `topic_name` from for
  the header, added one `getTopics()` fetch (on mount, independent of
  format) and look up the name by `topic_id` — `single_image`'s header
  still reads `proposal.topic_name`, unchanged.
- Loading state: added a `CAROUSEL_WAIT_STAGES` list and an elapsed-seconds
  ticker (only running while `generating && format === "carousel"`) so the
  wait shows staged reassurance text ("writing," then "likely done,
  generating the hero image next," then "styling the hero image now")
  instead of a static "Generating…" that would otherwise read as stuck
  during direct-write's longer, sequential (not parallel) end-to-end time
  — the real tradeoff already tracked in the deviations table, row 43-46.
  Thresholds (0/15/30/50s) are a reasonable estimate for reassurance text,
  not a measured progress bar making a precision claim. `single_image`'s
  button still just reads "Generating…", unchanged.

**Verified with a real UI tap-through, not a script bypassing the
frontend, and not code review alone** — this was explicitly required
given the earlier gap this closes was itself found by tracing code, not
by using the app. Ran the real local frontend (`next dev`) against the
real local backend (`uvicorn`), added temporary `print()` diagnostics to
`_generate_carousel_direct` and `_generate_for_brief` (removed
immediately after confirming — `git diff --stat` on `generate.py` shows
no residual diff), and had the actual app tapped through in a real
browser:
- Carousel: tap → `GET /topics` → straight to `POST /generate` with no
  `/generate/propose` call in between → `_generate_carousel_direct`
  invoked (confirmed by the temporary log line) → HTTP 200.
- Single image: tap → `POST /generate/propose` (200, preview step still
  runs) → "Generate" tap → `POST /generate` → `_generate_for_brief`
  (legacy `generate_post`) invoked, `format=Format.SINGLE_IMAGE` →
  HTTP 200.

Full backend suite 135/135 afterward (no backend code changed this
round — `generate.py`'s diagnostics were added and then fully reverted;
the real change is frontend-only).

**Not a blueprint deviation** — implements the scope boundary logbook #46
already documented as deliberate ("direct-write has nothing to preview
first") by giving carousel its own no-preview UI path, rather than
changing what that boundary means.

---

## 51. Paste-link ported to direct-write — its own writer variant, not a reuse of the taxonomy prompt as-is

**Symptom:** none in production — `_generate_for_brief()` (the function
`/generate/from-brief`, paste-link's own entry point, always called)
ignored `CAROUSEL_WRITER` entirely and always ran the legacy
`draft_post`/`critique_post`/`refine_post` chain, even after direct-write
became the taxonomy default (logbook #46). Requested explicitly as a real
feature port, not a bug fix — but treated with the same rigor, since
naively wiring the flag through would have shipped a content-grounding
regression (below).

**Why this isn't just plumbing — the anchor-selection rule doesn't fit a
real article:** the taxonomy direct-write prompt's rule 2 tells the model
to freely recall 3 candidate historical/cultural anchors from its own
knowledge and pick the strongest. Paste-link's brief has a real, specific,
pinned article (`brief.sources`) — free recall is exactly the wrong
instruction here; it would let the model wander into invented parallels
untethered to what the article actually says. Fixed by writing a real
paste-link-specific rule 2 (`_CAROUSEL_DIRECT_PASTE_LINK_ANCHOR_RULE`,
`engine/generator.py`): the anchor must be a specific fact, scene, moment,
or detail already stated in the pinned excerpt, not recalled or invented,
with an explicit instruction not to reach outside the excerpt for a
supporting parallel or statistic even a true one. Rules 1 and 3-12 (voice,
craft, punctuation) are about how to write, not where the anchor comes
from, so they transfer unchanged — refactored the existing
`_CAROUSEL_DIRECT_RULES` into `_CAROUSEL_DIRECT_RULE_1` +
`_CAROUSEL_DIRECT_TAXONOMY_ANCHOR_RULE` +
`_CAROUSEL_DIRECT_RULES_3_TO_12` so both variants compose from the same
shared 11-rule text rather than duplicating it (verified the composed
`_CAROUSEL_DIRECT_RULES` still produces 12 rules in order after the
split, before writing the new variant). Also softened the gendered-angle
instruction from the taxonomy prompt's hard requirement ("not acceptable"
to skip it) to conditional ("when the article's own content genuinely
supports one") — a hard requirement here would incentivize stretching a
real article's actual content to manufacture a gendered angle it doesn't
have, in direct tension with the whole point of this port.

**Citation grounding itself was NOT rebuilt** — `_citation_instruction_block`'s
`"sources"` branch (confirmed correct for this exact brief shape in
logbook #12) already embeds the full pinned excerpt into the prompt;
`_carousel_direct_paste_link_system_prompt` calls it exactly the way the
taxonomy path calls it for its own `citation_block`, no changes.

**Anchor avoid-list investigated, not assumed to transfer — found not
meaningfully applicable, left out:** `CarouselContext.recent_anchors`
(the taxonomy path's non-repetition mechanism) is built by matching
`MemoryRecord.topic_id` against a real, recurring `Topic.id`. Paste-link's
`topic_id` is `f"paste-link:{sha256(url or title)[:12]}"` — a one-off
hash unique to each pasted article. The only way it could ever find a
match is pasting the exact same URL or title twice. Beyond that, there's
no `Topic` object behind a paste-link brief at all, so
`assemble_carousel_context()` (which takes a `Topic`) can't even be
called — this isn't just "less useful here," it's structurally
inapplicable. `draft_carousel_direct_from_source()` therefore has no
topic/context parameters at all, rather than accepting dummy values for a
Topic that doesn't exist.

**A real, non-obvious bug caught by tracing validator.py, not assumed
away:** `build_paste_link_brief()` defaults `brief.approach` to
`Approach.STAT_RESEARCH` (used by the legacy path to pick a voice
register). Direct-write itself never reads `brief.approach` — but
`_finalize_generation`'s call to `validate_post()` independently calls
`slide_roles_for(brief)`, which uses `brief.approach` to decide
`carousel_body` (10-20 words) vs. `carousel_body_teaching` (35-50 words)
for the body slides. `STAT_RESEARCH` is not in `TEACHING_BODY_APPROACHES`
(`taxonomy/approaches.py`), so left uncorrected, `slide_roles_for` would
compute `carousel_body`'s narrow range while the actual slides are
`carousel_body_teaching`-shaped — guaranteed word-ceiling validation
failures on every real call, the same mismatch class logbook #44 already
found and fixed once for the taxonomy path. Fixed the same way: force
`brief.approach = Approach.STORY` in `_generate_paste_link_direct`
(`routes/generate.py`) when building the updated brief after the writer
call returns — `STORY` specifically because it's the one approach shared
by `CAROUSEL_V1_APPROACHES` and `TEACHING_BODY_APPROACHES`, the same
reason logbook #44 picked it. **Verified this was a real bug, not a
theoretical one**: ran the new test with the override temporarily removed
— it failed with exactly the predicted error (`slide 2/3/4 (carousel_body)
has 34 words, exceeds the 22-word ceiling`), then confirmed the fix
resolves it (`validation_errors == []`) before restoring it permanently.

**Deliberately NOT implemented by adding the `CAROUSEL_WRITER` check
inside the shared `_generate_for_brief`** — that function is also called
by `run_generate`'s own legacy fallback for taxonomy briefs (a preselected
angle, or `CAROUSEL_WRITER=legacy`), and a preselected angle must always
use legacy regardless of the flag (logbook #46's deliberate scope
boundary, re-confirmed live in logbook #50). Checking the flag inside
`_generate_for_brief` itself would have silently broken that boundary for
every `run_generate` caller, not just added support for paste-link.
Instead, added a new `run_generate_from_brief()` wrapper that branches on
`CAROUSEL_WRITER` before ever reaching `_generate_for_brief`, and pointed
`/generate/from-brief`'s route handler at it — `_generate_for_brief`
itself is completely unchanged.

**Fix, concretely:**
- `engine/generator.py`: split `_CAROUSEL_DIRECT_RULES` as described above;
  added `_CAROUSEL_DIRECT_PASTE_LINK_RULES`,
  `_carousel_direct_paste_link_system_prompt()`, and
  `draft_carousel_direct_from_source()`.
- `routes/generate.py`: added `_generate_paste_link_direct()` (the
  `generate_from_brief` analog of `_generate_carousel_direct`) and
  `run_generate_from_brief()` (the new branch point); `generate_from_brief`
  now calls `run_generate_from_brief` instead of `_generate_for_brief`
  directly.

**Verified with a real trial, not code review alone:** pasted a real,
live URL (`https://en.wikipedia.org/wiki/Impostor_syndrome`) through the
real local backend, `CAROUSEL_WRITER=direct_write` (the real default).
`POST /sources/paste-link` → real `POST /generate/from-brief` → real HTTP
200, a real generated post and a real hero image. Fact-checked every
specific claim in the output against the actual fetched excerpt line by
line: the "wrote down positive feedback, then had to recall why they
received it and what made them see it in a negative light" detail (body
slide 1) traces to the excerpt's Clance & Imes 1978 psychosocial-
intervention paragraph verbatim in substance; "first conceptualised...
high-achieving women... later research... equally distributed among the
genders... societal pressures, gender biases, traditional expectations"
(body slide 3 + caption) traces directly to the excerpt's "Gender
differences" section; "women may experience higher societal pressure...
male-dominated fields... gender-based discrimination or harassment...
depression and anxiety" (caption) traces directly to the same section's
next paragraph. No claim in the output was found unsupported by the
excerpt — zero fabrication beyond the article, the core requirement this
port exists to satisfy. Citation check passed cleanly (`_check_citation`
found no error — `requires_citation=True` and `_citation_mode(brief) ==
"sources"`, not `"none"`). Two unrelated, real validation flags did
surface and are reported rather than hidden: a forbidden-phrase hit on
the literal word "negative" (a pre-existing, aggressive `brand_kit`
entry that would fire for any writer, legacy or direct-write, unrelated
to this port) and one body slide 2 words under the 31-word floor (the
same mild-undershoot tendency already tracked as open in logbook #43-46's
deviations-table entry, now reconfirmed on this second writer variant).
Hero image: real GPT Image 2 + duotone render, genuinely on-brand
(abstract, editorial, a handwritten journal page with checklist marks)
and specifically tied to the chosen anchor ("positive feedback written
down"), not a generic or mismatched image.

Added two new tests (`tests/test_generate_route.py`):
`test_run_generate_from_brief_paste_link_direct_write` (confirms the
direct-write branch fires, `brief.approach` becomes `STORY`, and
`validation_errors == []`) and
`test_run_generate_from_brief_paste_link_legacy_override_still_works`
(confirms `CAROUSEL_WRITER=legacy` still works for paste-link and leaves
`brief.approach` at its real `STAT_RESEARCH` default, untouched). Full
backend suite: 137/137.

**Not a blueprint deviation** — implements `CAROUSEL_WRITER` consistently
across both of direct-write's real entry points, rather than changing
what the flag means.

---

## 52. Body-slide word floor wasn't holding — a stated number alone wasn't enough, added an explicit count-and-check step

**Symptom:** `carousel_body_teaching` slides (both taxonomy and paste-link
direct-write) kept undershooting the 31-word floor in real output —
first noticed in #44's own testing (2 of 4 fresh topics tripped it,
logged as "a real, unaddressed mild-undershoot tendency" at the time) and
confirmed still happening in live use since. The prompt already stated
the target as a number ("Target {lo}-{hi} words combined",
`_carousel_direct_body_distillation_instruction()`) — that alone wasn't
enough to hold the floor.

**Fix:** added an explicit count-and-check self-check step to the same
function, the identical pattern already hardened once for the isolated
POC's own rule 13 (`docs/direct-write-poc.md` Section 9 — a soft
"sparingly" instruction didn't hold there either, until it became an
explicit count-then-correct step with a hard cap). The new text
instructs the model to count each body slide's heading+beat words before
finalizing, and if under the floor, treat it as underdeveloped (not just
concise) and expand with one more concrete sensory or narrative detail
actually from that moment — explicitly not padding with a restated idea
or generic elaboration, since that would trade one failure mode
(undershoot) for another this prompt already rules out elsewhere (rule
9's beat-restatement check). Shared by both direct-write entry points
(`_carousel_direct_system_prompt` and
`_carousel_direct_paste_link_system_prompt` both call this same function),
so the fix applies to paste-link's port (logbook #51) too, not just the
taxonomy path this was first found on.

**Re-verified with fresh real trials, not just confirming the instruction
was added:** ran 5 fresh real `/generate` calls (`CAROUSEL_WRITER=direct_write`,
the real default) against a random sample of taxonomy topics spanning
both citation and non-citation requirements
(`society-invisible-labor`, `relationships-burnout`,
`wellness-stress-regulation`, `health-reproductive-health`,
`wellness-rest`) — real API calls, real Satori-shaped output, not mocked.
All 15 `carousel_body_teaching` slides across the 5 trials (3 per post)
landed inside the 31-55 word range; `validation_errors` was empty on
every single trial (previously 2 of 4 fresh topics tripped this same
floor under the old number-only instruction). Read the full caption and
all three body slides for two of the five trials in full to check the
self-check hadn't traded undershoot for padding/repetition — both read as
genuinely concrete and distinct beat-by-beat (e.g. "Four uneven lines in
blue ink," "camera face steady while her thumb moves over a tiny
square"), no generic filler or restated ideas found.

Full backend suite 137/137 (prompt-text-only change, no parsing/logic
touched, so the count is unchanged from logbook #51).

**Not a blueprint deviation** — a prompt-reliability fix for an already-
tracked, already-open issue (deviations table, row 43-46's "real,
unaddressed mild-undershoot tendency"), not a new design decision.

---

## 53. OPEN, EXPERIMENTAL — carousel direct-write's cover/body/closing prompt and schema rewritten (replaced, not appended), plus a real render bug found and fixed along the way

**What this is:** a deliberate rewrite of `draft_carousel_direct()`'s
cover/body/closing instructions and JSON schema — explicitly requested as a
*replacement*, not a layering of new rules on top of the old ones, since the
whole reason the carousel direct-write port (logbook #43-46) exists is to
avoid the checklist-accumulation problem that round-8 patching of the legacy
prompt (logbook #39) ran into. Every changed field/instruction below was
read in full first and then replaced outright:

- **Cover** — `headline_word`/`script_word`/`kicker` (three fields) replaced
  with exactly two: `headline` (a short *phrase*, not one isolated word —
  still lands in the same 96px slot the old one-word headline used) and
  `cover_body` (1-2 real sentences). `cover_body`'s instruction requires
  spelling out the category of any real named person/thing referenced
  (never assume familiarity), building curiosity by withholding *meaning*
  rather than basic facts, and — only when the anchor illustrates a
  separate real-life theme rather than being the subject in its own right —
  an explicit bridge sentence to the reader's own life.
- **Body** — the `heading` field is dropped entirely (not just left empty by
  convention; removed from the instruction and the JSON schema the model is
  shown). Each of the 3 body slides gains `accent_phrase`: an exact,
  verbatim substring of that slide's own `body` text, never more than one
  per slide, meant to be rendered emphasized in-line rather than as a
  separate label line. The instruction now also explicitly asks for
  flowing, full-sentence editorial prose (not clipped statements) and
  restates the beat-distinctness requirement at the body-slide level, not
  just the caption level.
- **Closing** — the old "one declarative line ... see rule 7" constraint
  (rule 7 required `closing_takeaway` to echo the caption's opening, at the
  level of one line) is gone. `closing_takeaway` is now a real 2-4 sentence
  build, explicitly *not* required to echo the opening, whose job is a new
  feeling for the reader — never a restatement of a body slide's image —
  in plain, direct language, with no wordplay for its own sake. Rule 7
  itself was edited down to only govern the caption's own ending, with an
  explicit parenthetical noting `closing_takeaway` now has its own separate
  instruction so the two don't silently stay coupled in a reader's mind.

**Schema/model changes, and why nothing was silently overloaded onto shared
state.** `CoverSlide`/`BodyTeachingSlide` (`app/models/post.py`) are shared
render components with the **legacy** chain (`generator.py`'s
`draft_post`/`critique_post`/`refine_post`), which still asks the model for
the old three cover fields and the old `heading`+`body` shape — confirmed by
reading `_build_slide()`, `_ROLE_FIELDS_EXAMPLE`, and `_brief_system_prompt`
before changing anything. Renaming or removing those fields outright would
have broken legacy's own still-live generation path (reachable via
`CAROUSEL_WRITER=legacy` and via any preselected-angle request, logbook #46).
Instead: `cover_body` and `accent_phrase` were added as new, optional
(`= ""`-defaulted) fields on the existing shared models — legacy's own raw
dict never supplies them, so they stay empty for every legacy-generated
slide; `_parse_carousel_direct_response` (the direct-write-only parser)
hardcodes `script_word`/`kicker`/`heading` to `""` on its own path rather
than the model requiring them to always be non-empty. Same reasoning on the
frontend: `CarouselCoverContent`/`CarouselBodyTeachingContent`
(`lib/types.ts`) gained the same two optional fields; `CarouselCover.tsx`
now renders `script_word`/`kicker`/`cover_body` conditionally (each only
when non-empty), which also fixed a latent issue the old code would have
hit the moment any of those three went empty: an unconditionally-rendered
empty `<span>` at a fixed `fontSize`/`lineHeight` still reserves that
line's vertical space, which would have left a visible gap where
`script_word`/`kicker` used to be for every direct-write cover.

**Word-range validation needed the same shared-vs-path-specific treatment.**
`validator.py`'s `_check_slide_word_range` keys its per-template floor/
ceiling purely off `role` (`carousel_cover`, `carousel_closing`), with no
concept of which writer produced the post — so a `closing_takeaway` sized
for a real 2-4 sentence build would have failed legacy's existing
`carousel_closing` range (10-20 words, tolerant 9-22) had that range simply
been widened in place, and conversely a genuinely short legacy takeaway
would start false-flagging as "too short" against a range built for
direct-write's longer prose. Fixed by adding `carousel_writer` as an
explicit, defaulted (`"legacy"`) parameter threaded through
`validate_post()` → `_check_format()` → `_check_slide_word_range()` →
a new `_range_for_role()` helper, which only consults the new
`_DIRECT_WRITE_WORD_RANGE_OVERRIDES` dict (`_CAROUSEL_DIRECT_COVER_WORD_RANGE
= (20, 45)`, `_CAROUSEL_DIRECT_CLOSING_WORD_RANGE = (24, 55)`, both with the
same 10%-tolerance treatment every other range already gets) when
`carousel_writer == "direct_write"`. `routes/generate.py`'s
`_finalize_generation()` gained the same defaulted parameter, threaded from
its two direct-write call sites (`_generate_carousel_direct`,
`_generate_paste_link_direct`) as `"direct_write"`; the legacy call site is
untouched and stays on the default. `carousel_cover` had no entry in
`_WORD_RANGE_FOR_ROLE` at all before this (legacy's one-word headline never
needed one, so it fell back to the flat `max_words_per_slide` cap) — it now
gets a real range, but only on the direct-write path.

**A real render bug found (not just theorized) during verification, and
fixed:** `CarouselBodyTeaching.tsx`'s `accent_phrase` highlight uses the same
word-by-word `flexWrap` technique `CarouselBody.tsx` already uses for its own
single emphasized phrase (necessary because Satori's flexbox-only layout
can't wrap text within a single non-word flex item — splitting into
per-word spans is what makes the paragraph wrap correctly at all). That
technique puts a fixed `columnGap` between every adjacent span, which is
only correct where the source text actually had a space. A real render
surfaced the bug directly: "...far less convenient ." and "...cold water
touch her face ." both rendered with a stray visible gap before the
trailing period, because the accent phrase's closing punctuation was glued
directly onto the source text with no space, but `columnGap` inserted one
anyway. **Fixed** by detecting punctuation glued directly onto either side
of the accent phrase (no space in the source) and folding it into the
accent span itself, so it shares that span's own flex item and gets no
`columnGap` before it, instead of becoming an orphaned same-color flex
sibling. Re-rendered both original repro cases plus 4 more body slides
across 3 more topics (including a mid-sentence comma case, "dressed as
reliability," followed immediately by more text) after the fix — all clean,
no stray gaps, in every case checked.

**Verified, in order:**
- Full backend suite: **143/143** (137 existing + 6 new — 3 in
  `test_validator.py` covering the writer-aware cover/closing range
  behavior including that the wider range still has a real ceiling, 3 in
  `test_generator.py` covering the new `_parse_carousel_direct_response`
  field mapping, including the case where `accent_phrase` genuinely isn't
  found in `body` — a real possibility, checked rather than assumed away).
- `pnpm exec tsc --noEmit`: clean, both before and after the render-bug fix.
- **5 real, unmocked `/generate`-shaped trials** (`draft_carousel_direct`,
  real `gpt-5.5` calls, not scripted responses) across
  `mindset-self-doubt`, `career-boundaries`, `wellness-stress-regulation`
  (citation-required), `inspiring-women-who-changed-history`
  (citation-required), and `relationships-invisible-labor`
  (citation-required) — `validation_errors: []` on every single trial.
  `headline` was a genuine multi-word phrase in all 5 (4-5 words each, not
  one word), `accent_phrase` was found as an exact substring of its own
  slide's `body` in all 15 body slides checked, and every `closing_takeaway`
  landed at exactly 3 sentences, in range, with no literal question and no
  restatement of a body slide's specific image.
- **The bridge-line instruction, generated for the first time (previously
  only reasoned through):** fired clearly in 2 of 5 trials
  (`mindset-self-doubt`: "The room did not know how to receive her mind.";
  `wellness-stress-regulation`: "It has something quiet to say about the
  body at work."), correctly did **not** fire on the one topic where the
  anchor genuinely IS the subject rather than illustrating a separate theme
  (`inspiring-women-who-changed-history` — Hedy Lamarr's own cover_body
  stayed entirely inside her own story, no bridge sentence, exactly as
  instructed), and was soft/ambiguous on the remaining 2
  (`career-boundaries`, `relationships-invisible-labor` — both cover_body
  paragraphs stayed curiosity-building but didn't include an unambiguous
  reader-directed sentence, even though their body slides do make the
  connection explicit a slide or two later). Reported plainly rather than
  rounded up: real, directionally working, not yet reliable 5-for-5.
- **Real Satori renders**, not just word counts: 5 real covers (checking the
  96px headline slot, previously sized for one word, against a genuine
  multi-word phrase) and 5 real closings (checking the 48px slot, previously
  sized for a short line, against a genuine 2-4 sentence build) rendered via
  the local `/api/render` route with real generated content. No overflow in
  any of the 10 — the longest cover (`inspiring-women-who-changed-history`,
  a 3-line headline + 3-line cover_body) and the longest closing (41-42
  words, 5 wrapped lines) both left generous margin before the hero-image
  slot / bottom of the canvas respectively. 8 real body-slide renders
  (`carousel_body_teaching` with `accent_phrase`) checked for the punctuation
  gap above, all clean after the fix.
- **A known, pre-existing, separate gap noticed while touching
  `editor/page.tsx`, not fixed here:** `SlideEditForm`'s `switch` has no
  `case "carousel_body_teaching"` at all, so body slides (both legacy's
  `heading`/`body` and direct-write's `body`/`accent_phrase`) have never
  been editable in the swipe-editor, on either writer. Pre-dates this
  change — confirmed by checking the switch statement, not assumed — and
  is out of this task's scope (fixing it well means deciding how
  `accent_phrase` should behave under edits, a real design question, not a
  one-line addition like the `cover_body` field this task did add to the
  cover's own edit form). Flagged here so it isn't rediscovered cold.
- **The known cross-topic anchor-convergence gap (deviations table, row
  43-46) recurred again in this trial batch, unprompted:**
  `mindset-self-doubt` and `inspiring-women-who-changed-history` both
  independently landed on the identical anchor ("Hedy Lamarr's
  frequency-hopping patent") on two different, unrelated topics in the same
  5-trial run. Not a new gap, not fixed here — additional real evidence for
  an already-tracked, still-open one.

Two new one-off scripts kept in the repo for reference, same practice as
`backend/scripts/poc_writer.py`: `direct_write_schema_trial.py` (calls
`draft_carousel_direct` directly against the real LLM for a fixed list of
topics and prints/saves the structured output) and `render_trial_slides.py`
(POSTs saved slide JSON to a locally-running `/api/render` for real PNGs).
Neither is imported by, or wired into, the app itself.

**Not a blueprint deviation beyond what logbook #43-46 already established**
— this is a content-quality iteration on an already-flagged
OPEN/EXPERIMENTAL feature, not a new departure from `blueprint.md`/
`implementation-guide.md`. `single_image` and the legacy carousel chain are
both completely untouched — confirmed by the full legacy-path test coverage
passing unchanged and by every new field/range being additive-and-defaulted
rather than replacing anything legacy reads or writes.

---

## 54. OPEN, EXPERIMENTAL — cover's bridge-line instruction hardened with the same requirement + self-check pattern as rule 1/rule 9; real-trial re-verification was blocked on both providers, then closed out at 2/2 once credits returned

**Symptom:** #53's bridge-line instruction (cover_body should bridge the
anchor to the reader's own life, except when the anchor is itself the whole
subject of the post) held only 2 of 4 in that entry's real testing — a soft
"add one explicit sentence" ask, not a checkable requirement. This is the
exact same failure shape rule 1 and the body-distillation word floor
(logbook #52) already went through before being hardened: a soft
instruction doesn't hold, an explicit "before finalizing, check X; if not,
add one now" self-check does.

**Fix:** `_carousel_direct_cover_instruction()` (`generator.py`) rewritten to
state the bridge line as an explicit requirement ("This is a requirement,
not an optional nicety") followed by the same checkable self-check pattern
already proven for rule 1 (docs/direct-write-poc.md Section 10) and the
body-distillation floor (logbook #52): "Before finalizing cover_body,
check: is the anchor itself the whole subject of this post, or does it
illustrate something else? If it illustrates something else, does
cover_body already contain a sentence connecting the anchor to the
reader's own life? If it does not, add one now." Not a reword-to-sound-
stronger change — the actual check step is new.

**Verified so far:** full backend suite 143/143 (prompt-text-only change,
no schema/parsing touched, so the count is unchanged from logbook #53).

**First verification attempt was genuinely blocked, not skipped:**
immediately after the code change, tried 6 fresh topics not used in #53's
trial (`mindset-perfectionism`, `mindset-rest`, `career-pay-scale`,
`career-perfectionism`, `wellness-burnout`, `wellness-sleep`) — the very
first live call failed with `openai.RateLimitError: insufficient_quota`
(429). Checked whether `provider="anthropic"` could stand in as a fallback
for this verification alone — it also failed immediately,
`anthropic.BadRequestError: "Your credit balance is too low."` Both
providers were out of credits at that point, a real account/billing state,
not a bug — the same category of blocker `docs/direct-write-poc.md`
Section 8 already hit. No trial results were fabricated or estimated in
place of real ones; asked whether to wait, top up credits, or log as
blocked — logged as blocked per that instruction.

**Closed out, on direct instruction to trim to 2 topics and report the
real number honestly, whatever it was** (a new standing rule for this
trial script going forward: 2 topics, not a larger batch). Credits had
returned by this point (confirmed live before running anything). Re-ran
`backend/scripts/direct_write_schema_trial.py` trimmed to exactly 2 fresh
topics — `mindset-perfectionism` and `career-pay-scale`, neither used in
#53's trial:

- `mindset-perfectionism` (anchor: girls'-needlework samplers) —
  cover_body: *"Girls once stitched samplers to prove patience,
  discipline, and skill. That old lesson still echoes when one imperfect
  sentence at work feels heavier than it should."* — explicit bridge
  sentence present. **Fired.**
- `career-pay-scale` (anchor: mad money) — cover_body: *"Mad money was
  cash a woman kept for a way home. Pay ranges can work the same way
  before a salary conversation begins."* — explicit bridge sentence
  present. **Fired.**

**Real result: 2/2**, up from 2/4 pre-fix. Reported plainly, not rounded
up past what the sample supports: 2 topics is a small sample, deliberately
smaller than #53's original 4-topic check (per the new 2-topic rule for
this script), so "2/2" is real evidence the requirement-plus-self-check
pattern is working the same way it already worked for rule 1 and the
body-distillation floor, not a claim the bridge line is now guaranteed
reliable at scale. `validation_errors: []` on both trials; both closings
landed at 3 sentences in range; all 6 body slides' `accent_phrase` values
were confirmed as real substrings of their own `body` text. Full backend
suite still 143/143 throughout (no code changed between the blocked
attempt and this run — only the trial script's own topic list, which isn't
part of the app).

**Not a blueprint deviation** — same classification as #53; this is a
prompt-reliability fix for an already-tracked, already-open issue, not a
new design decision.

---

## 55. Closing slide (S5) content derived from the caption's actual ending instead of a separate written-from-scratch field, plus a stale single-line edit form fixed to a textarea

**Symptom 1 (content):** real testing kept showing `closing_takeaway`
(logbook #53's real 2-4 sentence build) read weaker and more generic than
the caption's own actual final sentences — the exact problem the body
slides already solved (logbook #19/#43): a field written as new,
from-scratch content is a worse writing task than adapting something the
model has already written well. `closing_takeaway`'s own instruction
literally told the model to invent "a new feeling... hasn't already stated
outright," directly working against reusing the caption's own strong
ending.

**Fix 1:** `_carousel_direct_closing_instruction()` (`generator.py`)
rewritten to the same derive-not-invent pattern the body-distillation
instruction already uses: `closing_takeaway` is now explicitly the
caption's own actual final beat — same image, same idea — closely adapted
for its own slide, never copied verbatim, never a new conclusion invented
separately. The old "new feeling... hasn't already stated outright"
framing was removed outright, since it directly contradicted deriving from
what the caption has, in fact, already stated. Prompt-text-only change,
same JSON field, no schema/model/validator change — full backend suite
still 143/143.

**Symptom 2 (UI):** the swipe-editor's edit form for the closing slide
(`SlideEditForm`, `editor/page.tsx`) rendered `takeaway` in a single-line
`<input>`, a leftover from before logbook #53 made it a real 2-4 sentence
value — every other multi-sentence-capable field in the same file
(`carousel_conversation`'s `question`, `single_quote`'s `quote`) already
uses the `multiline` prop (a `<textarea>`), `carousel_closing` was the one
case still missing it.

**Fix 2:** added `multiline` to that one `Field` usage — same component,
same pattern, no new styling invented. `pnpm exec tsc --noEmit`: clean.

**Verified, max 2 real trials per the standing rule:** `wellness-sleep`
(anchor: factory night-shift whistle) and `mindset-rest` (anchor: the
invention of the weekend), neither used in any prior trial batch.

- `wellness-sleep` — caption's actual ending: *"But the body is not a
  factory whistle... It keeps asking for darkness, repetition, and a
  gentler end to the day..."* → closing: *"A body is not a whistle on a
  brick wall... It still asks for darkness, steadiness, and an ending it
  can recognize."* Same image, same idea, genuinely reworded — clean.
- `mindset-rest` — caption's actual ending: *"...It simply struck the
  hour, and for a moment, the machines went quiet..."* → closing: *"...It
  struck the hour while there was still life left in them..."* Mostly
  reworded, but **"It struck the hour" is a near-verbatim 4-word lift**
  from the caption's "It simply struck the hour" (missing only "simply") —
  reported plainly, not glossed over, the same discipline logbook #44
  already applied to a similar minor near-verbatim finding. Not a full-
  sentence copy, but a real, partial overlap worth watching for on future
  trials.

Both trials: `validation_errors: []`, 2-4 sentences each (3 and 3), within
the existing word range, no restatement of a body slide's own specific
image, never phrased as a question. The bridge-line instruction (logbook
#20, unchanged by this task) also fired cleanly on both, incidentally
confirming it's still holding.

**UI verification — a real render, not just code reading, despite not
having a way to drive the real authenticated `/editor` page in this
session:** `AuthGate` (`components/AuthGate.tsx`) requires a real Supabase
session with no credentials available to this session to obtain one — the
identical constraint logbook #13 already hit for the POC's own page.
Followed that entry's own established precedent instead of skipping
verification: built a faithful static HTML reproduction of the
`carousel_closing` edit form using the real, verbatim CSS values from
`lib/ui-styles.ts` (`cardStyle`/`labelStyle`/`inputStyle`) and the real
41-word closing text from the `mindset-rest` trial above, then rendered it
with a real headless Chromium (Playwright, already installed in this
environment from a prior session per logbook #24) and took a real
screenshot — not simulated. Confirmed visually and programmatically: the
old single-line input clips the text mid-word ("...prove they v"); the new
textarea wraps the full text across visible lines and is scrollable/
resizable; the underlying value is byte-identical between both (227
characters, unmodified) — nothing was ever actually truncated at the data
level, only the old input's display was unreadable. Honestly noted, not
glossed over: at the textarea's default `minHeight: 70`, the last line of
a full 4-sentence closing sits just below the visible fold without
scrolling or resizing — identical behavior to the already-proven `Quote`
field at the same `minHeight`, not a new regression this fix introduced.

**Not a blueprint deviation** — a content-quality and UI-staleness fix on
an already-tracked, OPEN/EXPERIMENTAL feature (logbook #43-46, #53-54),
not a new design decision.

---

## 56. Full aesthetic pass on every carousel template the direct-write port actually uses — airier leading, top-anchored layout, a cover swipe marker, and closing-specific weight/responsive sizing

**Scope, decided explicitly, not guessed at silently:** "every carousel
template" is read here as every template the carousel direct-write port
(logbook #43-46) actually produces — `CarouselCover`, `CarouselBodyTeaching`,
`CarouselClosing`, `ConversationSlide` — not `CarouselBody` (legacy's
non-teaching fragment shape, never reached by direct-write) and not
`single_image`'s `SingleQuote`/`SingleStat`, consistent with every task in
this arc since #19 explicitly scoping to direct-write and leaving
`single_image`/legacy-only shapes untouched. All four templates are shared
render components with the legacy chain (same `template_id`, same React
component), so these are pure rendering/typography changes with no content-
generation logic touched — they apply to legacy-produced carousels too, by
construction, not by a separate decision.

**Changes, per template:**
- **Every template:** line-height increased for airier reading (cover
  headline 1→1.1, script_word 1.15→1.2, kicker/cover_body 1.35→1.4/1.5;
  body-teaching's body 1.5→1.6; closing 1.3→1.4; conversation's question
  1.3→1.4, cta 1.4→1.5, invite gained an explicit 1.2 where none existed
  before). `CarouselBodyTeaching`, `CarouselClosing`, and `ConversationSlide`
  changed from a vertically-centered `flex:1` wrapper to a top-anchored one
  (`justifyContent: "flex-start"` + a fixed `marginTop: 56`, matching
  `CarouselCover`'s own already-proven convention) — a centered block reads
  as a small floating island with equal empty margins above and below that
  shrinks or grows with word count; top-anchoring fixes the position readers
  land on to be consistent regardless of length, with any slack now falling
  only at the bottom. **A real, explicit deviation from blueprint.md Section
  12's "center within that wrapper" convention for this template family** —
  logged here, not silently reverted, same treatment as #32's masthead
  simplification.
- **Body-teaching also got a static font-size increase (36px → 44px)**, on
  top of the layout/leading changes above — a real render at the template's
  own 55-word ceiling still showed roughly half the frame empty at 36px, so
  the top-anchor alone wasn't enough to satisfy "fills more of the available
  space"; 44px is a fixed bump (not content-length-responsive, that
  mechanism is reserved for closing specifically, per this task's own
  scoping) and was re-verified not to overflow at the ceiling.
- **Cover** gained a swipe marker between the text block and the hero image:
  plain ASCII "Swipe >" text, small-caps styled to match the masthead/label
  convention already used elsewhere. **A first attempt used a CSS
  border-triangle (transparent top/bottom borders + a solid left border,
  the standard browser technique for a zero-size triangle) and a real render
  showed it rendering as a plain filled square instead of a triangle** —
  Satori's border implementation doesn't replicate a browser's diagonal
  border-miter clipping. Fixed by dropping the CSS shape entirely and using
  plain ASCII text only, consistent with this project's own established
  practice (logbook #39 round 7: an emoji/em-dash/middot/hedera/star glyph
  all rendered as tofu in this project's bundled font subset, fixed the same
  way, by falling back to plain ASCII).
- **Closing (S5)** specifically: `fontWeight` reduced 700 → 600 (too heavy
  at the original weight), and `fontSize` is now responsive to `takeaway`'s
  own word count via a new `closingFontSize()` helper — a linear scale from
  48px (near the 21-word tolerant floor) down to 36px (at the 61-word
  tolerant ceiling), computed in JS since Satori has no `clamp()`/`calc()`
  support to lean on.

**Real render checks at both ends of each template's word range, not just
one example, per this task's explicit ask** — using exact, programmatically
verified word counts (a `make_text()` helper that glues periods/commas onto
existing tokens rather than inserting new ones, so `len(text.split())`
always matches the target count exactly, asserted, not assumed) rather than
hand-counted strings:

| Template | Floor render | Ceiling render |
|---|---|---|
| `carousel_cover` | 18 words (4 headline + 14 body) — clean | 50 words (6 headline + 44 body, 4-line headline) — **hero image clipped at the bottom edge**, a real overflow found by this exact test |
| `carousel_body_teaching` | 31 words — clean, though still leaves real trailing space below (see below) | 55 words — clean, no overflow at the new 44px size |
| `carousel_closing` | 21 words (renders at 48px) — clean | 61 words (renders at 36px) — clean, comfortably fits 6 lines |
| `carousel_conversation` | 13 words — clean | 28 words — clean |

**The one real overflow found, investigated, and characterized rather than
left as an unqualified failure:** the cover-ceiling case above only clipped
the hero image when the headline itself wrapped to 4 lines (an unusually
long 6-word headline). A follow-up render at the identical combined 50-word
ceiling, but with a headline length matching what every real trial in this
document and #19-22 has actually produced (3-5 words, 1-2 lines), rendered
cleanly with the full hero image visible. **Not fixed** — narrow edge case,
real but not reproducible with realistic model output, flagged rather than
silently ignored or overclaimed as fixed.

**2 real, unmocked `/generate`-shaped trials** (`career-imposter-syndrome`,
anchor: blind auditions in orchestras; `wellness-burnout`, anchor: canary in
a coal mine — the latter a **repeat of the already-tracked cross-topic
anchor-convergence gap**, deviations table row 43-46, recurring again
unprompted) — both `validation_errors: []`, both rendered cleanly across
every slide (cover, all 3 body, closing, conversation) at the new settings.
Punctuation confirmed rendering cleanly on real content, not just
synthetics: apostrophes ("musician's," "miner's"), a semicolon, commas, and
question marks all rendered correctly with no tofu or spacing artifacts —
including the `accent_phrase` punctuation-glue fix from #19, re-confirmed
still holding under the new 44px size.

**Not fixed, honestly noted:** even after the layout and font-size changes,
a body-teaching slide at the true floor of its word range (31 words) still
leaves visible empty space below the text — an inherent consequence of a
fixed 1080×1350 canvas paired with a real word-count range that has a
genuine floor, not a bug a static font/leading change can fully eliminate
without either responsive sizing (deliberately scoped to closing only) or
a canvas/aspect-ratio change (out of scope). Reported as a real, bounded
tradeoff, not glossed over as fully solved.

Full backend suite 143/143 (no backend code touched — only the two
reference scripts' topic lists). `pnpm exec tsc --noEmit`: clean throughout,
including after the swipe-marker fix.

**Not a blueprint deviation beyond the explicit one named above** — the
layout/centering change for body-teaching/closing/conversation is the one
real, named departure from blueprint.md Section 12; everything else
(leading, font-size, weight, the swipe marker) is typography/decoration
`implementation-guide.md` never locked a specific value for.

---

## 57. Swipe-editor gained a real edit form for `carousel_body_teaching` slides — a pre-existing gap flagged twice (logbook #19, #53) and never fixed until now

**Symptom:** `SlideEditForm` (`editor/page.tsx`) has a `switch` on
`slide.template_id` with a case for every template except
`carousel_body_teaching` — the 3 body slides of every carousel (both
legacy- and direct-write-produced) had no edit form at all in the
swipe-editor. Not a new bug: logbook #19 first noticed the switch was
missing this case while adding `accent_phrase`, and #53 re-noticed it while
fixing the closing slide's edit form, both times flagging it as a real,
pre-existing gap out of scope for the task at hand rather than silently
fixing it inline.

**Fix:** added the missing case, matching the exact `Field`/`cardStyle`
pattern every other case already uses. Three fields: `Heading` (legacy-only,
typically empty on the now-default direct-write path — shown
unconditionally, same reasoning as `cover_body`'s field on the cover's own
form), `Body` (multiline, since body-teaching's real content is 1-2 full
sentences, not a short line), and `Accent phrase` (single-line, since it's
meant to be a short substring, not a paragraph). Editing `body` freely can
desync it from `accent_phrase` (no longer a real substring of the edited
text) — accepted, not specially guarded against: `CarouselBodyTeaching.tsx`
already falls back to a plain, unsplit body render whenever `accent_phrase`
isn't found in `body` (task "#19"), so a desync degrades gracefully to
"no highlight" rather than breaking the render or losing content.

**Verified with a real functional check, not a visual render pass, per
this task's explicit ask.** `AuthGate` blocks driving the real `/editor`
page with actual credentials in this session (the same constraint hit in
#22/#55) — rather than falling back to a static reproduction again (right
for a pure-CSS concern, not for "does an edit actually save and reflect"),
used a different, still-legitimate technique suited to a *functional*
check: a structurally-valid but cryptographically-unverified fake Supabase
session injected into `localStorage` (`sb-<project-ref>-auth-token`,
Playwright's `addInitScript`, so it's present before the page's own JS
runs). `AuthGate` only calls `supabase.auth.getSession()`, which resolves
from local storage without a network round-trip when the session isn't
expired — no real credentials were used or bypassed server-side, and
nothing in the editor flow being exercised here (no regenerate/reshuffle
triggered) makes any authenticated Supabase network call that a fake token
could affect. A real `GenerateResponse` from an actual prior `/generate`
trial (`wellness-burnout`, task "#23") was seeded into `sessionStorage` the
same way `session-store.ts` itself writes it.

With that, a real headless Chromium (Playwright, already installed from
prior sessions) actually loaded `/editor`, confirmed it was **not**
redirected to `/login` (the fake session was accepted), navigated to the
first body-teaching slide via its real dot control, and confirmed
end-to-end, against the real rendered DOM, not assumptions:

- The edit form appears with `Heading`/`Body`/`Accent phrase` fields.
- Typing a marker into `Body` and reading it back from the *live preview*
  (the actual `SlideRenderer`/`CarouselBodyTeaching` component, the same
  one `/api/render` uses) confirms it: the edit reached real React state
  and re-rendered, not just an isolated form-field echo.
- Editing `Accent phrase` to a different real substring of the body
  ("small enough," verified present in this slide's actual text) and
  querying the real rendered DOM's computed CSS color confirmed the
  highlight genuinely moved: the old phrase ("poisoned air") lost the
  accent color, the new one gained it — not just that new text appeared
  somewhere on the page, which would be true regardless of highlighting.
- Both fields still held their edited values after the re-render (a real
  save into state, not a UI glitch that silently reset).

**A real bug in the test itself, not the app, caught and fixed along the
way:** the first version of this check used `.locator("input").last()` to
find the Accent phrase field, which silently grabbed the page's unrelated
Hashtags input instead (`"#burnout #wgs"`) — the page has multiple
`<input>`/`<textarea>` elements (Heading, Accent phrase, Caption,
Hashtags), and position-based selection picked the wrong one without
erroring. Fixed by scoping the locator to the "Edit this slide" section
specifically and indexing within it by the known field order, after
`getByLabel()` (the more idiomatic fix attempted first) timed out
unresolved against this component's label-wrapping markup.

**A second, more important false alarm caught and correctly not treated as
a bug:** an early version of this check set `accent_phrase` to an invented
string ("ACCENT-EDITED") not actually present in `body`, and then
(correctly) found it never appeared anywhere in the rendered preview.
Investigated before assuming a bug: this is exactly
`CarouselBodyTeaching.tsx`'s own documented fallback behavior from task
"#19" — an `accent_phrase` that isn't a real substring of `body` renders
as plain, unhighlighted text, not an error and not a silent no-op. The
check was rewritten to edit `accent_phrase` to a genuinely findable
substring instead, which is what actually exercises the edit-and-reflect
behavior this task asked to confirm.

Full backend suite unaffected (143/143, no backend code touched).
`pnpm exec tsc --noEmit`: clean.

**Not a blueprint deviation** — closes a documented UI gap on an
already-tracked feature; no design decision changed.

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
| 30 | `voice_samples.direct` rewritten to be domain-diverse instead of the originally "Locked" (blueprint Section 4) workplace-themed 5 samples | Live-repro-confirmed as the dominant driver of content drift (accepted angles pivoting to invented office/meeting scenarios) — the locked value was actively working against the product's own quality goal |
| 32 | Masthead shows only `masthead_short` ("WGS") — the `{category} NO. {n}` text and its rule/separator, specified in blueprint Section 12, are no longer rendered | Explicit request to simplify what she sees on every slide; backend computation is untouched, so this is reversible in one file |
| 25 | Browse screen rebuilt as category-first, strict `primary_category` filtering — no more flat multi-tag topic list | Keeps the browse category and the masthead's counted category always consistent; blueprint Section 5's multi-tag display could show the same topic under a category tile that doesn't match its actual masthead label |
| 39 | **OPEN/EXPERIMENTAL, 8 review rounds in** — carousel's sampled approach pool restricted to `story`/`question_reflection` only, its system/critique prompts swapped to a connected micro-essay arc in place of the generic specificity/actionability/saveability checklist; CTA-flagging, truncation, and closing-declarative all hold cleanly; rounds 5–6 fixed reader-address/anchor/hedge issues; round 7 added a real `carousel_conversation` slide (first structural, not prompt-only, change) and fixed a render-time emoji glyph gap; round 8 raised body slides 1–2 → 3 (6 slides total now, fixed regardless of approach), removed the hardcoded "with you," from display, relocated the real `brand_kit`-driven follow-us/handle line from the closing slide to the conversation slide (the true last slide as of round 7), added anti-padding/split guidance (adapted from an audited pattern in another project) and a 10% word-budget tolerance, corrected same-round to be carousel-only (was briefly universal by mistake) and extended to `validator.py` so the app's own warning banner agrees with what the model is told | Creator feedback that carousel output felt fragmented, no single throughline; `single_image` deliberately untouched; all rounds implementation/local-verification only so far, none yet run through a real `/generate` call |
| 40 | Production text generation (`LLMProvider`, all callers) defaults to `gpt-5.6-luna`/`gpt-5.5` (OpenAI) instead of the locked Claude Haiku 4.5/Sonnet 5 | Anthropic production credits ran out entirely, plus real A/B evidence gpt-5.5 matched/beat Sonnet 5 on anchor authenticity and voice discipline; Claude path fully preserved and reversible via `LLM_PROVIDER=anthropic`, no redeploy needed |
| 43-46 | **OPEN/EXPERIMENTAL** — carousel direct-write port (single-call writer, no critique/refine, free anchor pick guided by category+seed_angles) now wired into `routes/generate.py` as the default (`CAROUSEL_WRITER=direct_write`) for carousel, replacing the legacy chain for that call; its hero image generation runs **sequentially after** the text call, not in parallel — a direct deviation from blueprint Section 15's "text and image generation run as independent parallel lanes off the same brief" design, for carousel direct-write specifically (the legacy chain and `single_image` are both unaffected and still run their lanes in parallel as originally specced). Cross-topic anchor-convergence (independent generations landing on the same anchor, e.g. `career-burnout`/`wellness-burnout` both choosing "canary in a coal mine") is a real, still-open, still-unfixed gap, reconfirmed in this now-production-wired code path, not just the isolated POC it was first found in (`backend/app/poc/FINDINGS.md` #1). Both the sequential-image tradeoff and the anchor-convergence gap now also apply to paste-link's own direct-write entry point (logbook #51), which reuses the same single-call, sequential-image design — not a second, separate deviation, the same one now confirmed at a second entry point | Real testing found direct-write's single call outperformed 8 rounds of patching the legacy checklist prompt (`docs/direct-write-poc.md` Section 5); sequential image generation is a structural consequence of the single-call design, not a choice — mood/visual_subject aren't known until the one writer call returns, unlike the legacy chain's cheap-tier pre-sample that knows them before the strong-tier draft even starts; reversible via `CAROUSEL_WRITER=legacy`, not a hard cutover; anchor-convergence has no fix yet on either path (POC or production-wired) |
| 53 | **OPEN/EXPERIMENTAL** — carousel direct-write's cover is now `headline`+`cover_body` (was `headline_word`/`script_word`/`kicker`), body slides drop `heading` in favor of an in-line `accent_phrase` (an exact substring of that slide's `body`), and `closing_takeaway` is a real 2-4 sentence build (was a one-line echo of the caption's opening) instead of legacy's short-takeaway shape. `CoverSlide`/`BodyTeachingSlide` (shared render models with legacy) gained these as new optional, defaulted fields rather than having anything renamed/removed out from under legacy, which still uses the old shapes unchanged; `validator.py` gained a `carousel_writer`-gated word-range override (`_DIRECT_WRITE_WORD_RANGE_OVERRIDES`) so legacy's own, shorter cover/closing ranges are untouched. Bridge-line instruction (cover_body should bridge to the reader's life only when the anchor illustrates a separate theme) generated for the first time on 5 real trials: fired clearly on 2, correctly stayed silent on 1 (an anchor-IS-the-subject topic), soft/ambiguous on 2 — real but not yet reliably 5-for-5. Cross-topic anchor convergence (row 43-46) recurred again, unprompted, on 2 of the 5 trial topics | Explicit request to replace (not layer onto) the cover/body/closing instructions, since layering was exactly the checklist-accumulation failure mode direct-write was built to escape (see logbook #39's own diagnosis, `docs/direct-write-poc.md` Section 2); real render verification (not just word counts) also surfaced and fixed a genuine Satori rendering bug (a stray gap before punctuation glued directly onto `accent_phrase` with no source space) |
| 56 | `CarouselBodyTeaching`, `CarouselClosing`, and `ConversationSlide` changed from vertically-centered `flex:1` content to top-anchored (`flex-start` + fixed `marginTop`), matching `CarouselCover`'s convention | Centered content read as a small floating island with equal empty margins above/below that shrank or grew with word count; top-anchoring fixes the reading position regardless of length. Since these are shared render components, this also changes legacy-produced carousels' appearance, not just direct-write's |
