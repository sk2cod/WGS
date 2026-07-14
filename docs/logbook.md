# Logbook — Phase 6 deployment & post-deploy fixes

Change log of every issue reported after Phase 6 (Deployment) went live, what actually
broke, how it was fixed, and where the fix deviates from `blueprint.md` /
`implementation-guide.md`. Written after the fact from the deployment session — treat
`CLAUDE.md`'s "Working notes" as the current operating rules; this file is the history
of how we got there.

---

## 1. Initial Phase 6 deployment

**What was built, exactly per `implementation-guide.md` Section 10:**
- Backend deployed to Railway (project `wgs-backend`), `uvicorn app.main:app` via `railway.json`.
- Frontend deployed to Vercel (project `wgs`).
- `CORSMiddleware` restricted to `FRONTEND_ORIGIN`, updated to the real Vercel URL and redeployed once the frontend existed (the guide's specified sequencing).
- Supabase schema created: `brand_kit`, `memory`, `image_cache` tables + `heroes` Storage bucket (`backend/app/db/schema.sql`), plus `backend/app/db/supabase.py` (client + queries) and `frontend/lib/supabaseClient.ts`.
- `DEPLOY.md` written documenting the click-path.

**Deviation — domain naming:** the guide didn't anticipate the requested project name (`wgs`) being available as a Vercel project but not as a bare `wgs.vercel.app` subdomain (`.vercel.app` names are global across all Vercel users, independent of per-account project names). Vercel auto-assigned `wgs-two.vercel.app` as the project's default domain; `wgs-studio.vercel.app` was separately registered as a proper project domain to serve as the clean canonical URL. Both domains exist and both matter — see #6.

**Deviation — Vercel deployment protection:** new Vercel projects default to SSO/authentication protection on non-custom domains, which would have blocked the creator from ever loading the app on her phone. Disabled via `vercel project protection disable wgs --sso` — not mentioned in the guide since it predates this Vercel account default.

---

## 2. Railway env vars only partially applied

**Symptom:** after the first backend deploy, only `FRONTEND_ORIGIN` was actually set on Railway — `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `SUPABASE_*`, and 8 other keys were silently missing, even though the push command reported success for all of them.

**Root cause:** the bulk `railway variable set` loop didn't pass `--service wgs-backend`. Without an explicit service target, the sets appeared to succeed but didn't persist against the real service.

**Fix:** re-ran the push with `--service wgs-backend` on every call, verified all 12 keys were present via `railway variables --kv` before redeploying.

**Not a blueprint deviation** — implementation detail of the CLI, not the architecture.

---

## 3. `/generate` intermittently 500ing with `JSONDecodeError`

**Symptom:** `POST /generate` (the strong-tier, Sonnet-driven path) failed roughly 1 in 3 calls with `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)` in `_parse_post`. The cheap-tier `/generate/propose` (Haiku) never failed.

**Root cause:** `claude-sonnet-5` defaults **extended thinking** on when the `thinking` param is omitted, with an uncontrolled internal token budget. That budget can consume the entire `max_tokens` allotment, leaving zero tokens for the actual JSON response — confirmed directly: one repro run showed `stop_reason: max_tokens`, `content block types: ['thinking']` only, no `text` block at all.

**Fix:** `backend/app/providers/llm.py` now passes `thinking={"type": "disabled"}` on every Anthropic call (both tiers, one shared `complete()` method). Verified via repeated live-API calls: 5/5 direct `draft_post` calls succeeded cleanly post-fix, versus failing before it.

**Not a blueprint deviation** — a real-model-behavior bug, not a design choice. `implementation-guide.md` predates `claude-sonnet-5`'s extended-thinking default.

---

## 4. Login screen + Row Level Security (explicit follow-up request, beyond Phase 6's written scope)

`implementation-guide.md` Section 10's Phase 6 "Build" list only calls for the Supabase schema, storage bucket, and one auth user to exist — it does not call for a login UI or RLS policies. Both were added afterward on direct request:

- `frontend/app/login/page.tsx` + `frontend/components/AuthGate.tsx`: gates every route behind a Supabase Auth session (client-side check + redirect), wired to the one real auth user created directly in the Supabase dashboard.
- RLS enabled on `brand_kit`, `memory`, `image_cache` (`backend/app/db/schema.sql`): full access for the `authenticated` role, none for `anon`. The backend's `service_role` key bypasses RLS entirely, so this only closes off the public `anon` key that ships inside the frontend JS bundle.
- Verified with a throwaway test user (created, exercised, then deleted): anon reads return empty/`401`, authenticated reads/writes succeed.

**Deviation:** this is new functionality, not in the original design docs. Recorded here rather than silently folded into "Phase 6 as originally scoped."

---

## 5. Memory + Brand Kit migrated from local disk to Supabase (explicit follow-up request)

Also beyond Phase 6's literal build list — `engine/memory.py`'s own docstring before this change said outright: *"File-backed for now — no Supabase wiring until Phase 6 — but kept behind a small store class so swapping the backing store later doesn't touch callers."* Phase 6 as literally written only asked for the schema and a typed client to exist, not for the engine to actually use them. This was completed as a follow-up migration:

- `MemoryStore()` (no `path` arg — how every route constructs it) now reads/writes the real Supabase `memory` table.
- `MemoryStore(path=...)` (how every test constructs it) is unchanged — still file-backed, still fully hermetic, zero test changes needed beyond this.
- `taxonomy/wgs_brand_kit.get_brand_kit()` added: reads the `brand_kit` row from Supabase, self-seeding it from the existing `WGS_BRAND_KIT` constant on first call (no separate seed script). Routes swapped the constant for this accessor.
- **Verified against an actual restart, not just a same-process read/write:** seeded one `status="exported"` record directly in Supabase, confirmed the masthead counter reflected it (`MINDSET NO. 02`) via a live `/generate` call, ran a real `railway up` (full container rebuild — Railway's local filesystem is wiped on every redeploy, which is exactly what the old file-backed store couldn't survive), then confirmed the masthead counter was *still* `MINDSET NO. 02` post-restart and the exact seeded row (by ID) was still present.

**Not a blueprint deviation in the architectural sense** — this is precisely what Section 9 of the guide describes as the target state. It's logged here because it happened as an explicit later request, not inside the original Phase 6 pass.

---

## 6. Vercel domain confusion: removing `wgs-two.vercel.app` broke the dashboard

**What happened:** asked whether `wgs-two.vercel.app` (Vercel's auto-assigned default domain, see #1) served any purpose beyond `wgs-studio.vercel.app` (the deliberately registered canonical domain). Nothing in code, CORS config, or docs referenced it, so it was removed via `vercel alias remove`.

**Symptom:** the Vercel dashboard's project Overview then showed no production domain at all, and the Deployments tab stopped highlighting any deployment as "Production" — even though the app itself kept serving fine the whole time through `wgs-studio.vercel.app` (dashboard bookkeeping and actual request routing are two separate systems in Vercel, and they diverged).

**Root cause:** `wgs-two.vercel.app` isn't a discardable duplicate — Vercel bakes one auto-assigned `.vercel.app` domain into a project's metadata as *the* canonical default. `vercel project ls` kept reporting it as the "Latest Production URL" even after deletion (a dead reference, not a live fallback to another domain). Deleting it broke the dashboard's domain/production bookkeeping without breaking actual traffic routing.

**Fix:** restored the alias (`vercel alias set <deployment> wgs-two.vercel.app`); dashboard returned to normal immediately.

**Lesson, not a deviation:** don't remove Vercel's auto-assigned default `.vercel.app` domain even when nothing in the codebase references it directly.

---

## 7. Phone report: "Load failed" on Generate

**Symptom:** tapping Generate on a real topic (carousel format) on a phone produced a generic "Load failed" — the message a mobile browser's `fetch()` throws on a genuine network-level failure (timeout/dropped connection), not a clean HTTP error response.

**Investigation:** measured the full `/generate` pipeline directly against production, isolating each stage:
- Text lane (draft → critique → refine, three serial Sonnet calls): a stable ~29.5s.
- Image lane (GPT Image 2 at `IMAGE_QUALITY=medium`): **39–112 seconds, highly variable**, including one call that didn't finish inside a 2-minute window.

Since the two lanes run in parallel (`asyncio.gather`), total request time is `max(text, image)` — so the image lane, not the text lane, was the dominant and most variable cost, easily explaining a mobile timeout.

**Fix:** switched `IMAGE_QUALITY` from `medium` to `low` after visually confirming the duotoned output is indistinguishable (this was already flagged in `CLAUDE.md` as a planned-but-not-yet-run experiment). Re-measured live: **consistently 20–32 seconds**, no more 100+ second outliers. Also ~8x cheaper per the guide's own cost section.

**Not a blueprint deviation** — this is the experiment `implementation-guide.md`'s cost guardrails section explicitly anticipated ("Start medium; run the duotone A/B early and, if indistinguishable, set low").

---

## 8. "render failed for carousel_cover: 500" on Export

**Symptom:** after fixing #7, generation succeeded but tapping Export failed with `render failed for carousel_cover: 500` from `lib/render-client.ts`.

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

## Summary — deviations from the original design docs

| # | Deviation | Why |
|---|---|---|
| 1 | Two Vercel domains in play (`wgs-two.vercel.app` auto-assigned default + `wgs-studio.vercel.app` canonical) instead of one clean URL | `wgs.vercel.app` was already taken globally; Vercel's auto-assigned fallback can't be removed without breaking dashboard bookkeeping |
| 4 | Login screen + RLS added | Explicit follow-up request, not in Phase 6's written "Build" list |
| 5 | Memory/brand kit actually wired to Supabase (not just schema+client existing) | Explicit follow-up request; Phase 6 as literally written stopped short of this |
| 7 | `IMAGE_QUALITY=low` instead of the doc's starting `medium` | The guide's own planned experiment, now run and confirmed |
| 8 | Frontend builds with `--webpack`, not Next 16's default Turbopack | Turbopack silently drops a file `@vercel/og` needs at runtime on Vercel; webpack doesn't |
