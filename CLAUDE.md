# WGS — Women's Growth Society Content Studio

AI-assisted Instagram carousel/post generator for a single creator brand (WGS). Full spec lives in:

- `docs/blueprint.md` — product design, taxonomy, generation pipeline, design system
- `docs/implementation-guide.md` — folder structure, Pydantic contracts, phase-by-phase build plan

**Always read both docs in full before starting or resuming work on any phase.**

---

## Current status

- ✅ Phase 1 (Design foundation) — complete, verified PASS
- ✅ Phase 2 (Data spine) — complete, verified PASS
- ✅ Phase 3 (Generation) — complete, verified PASS
- ✅ Phase 4 (Surfaces) — complete, verified PASS
- ✅ Phase 5 (Mobile flow) — complete, verified PASS
- ✅ Phase 6 (Deployment) — complete, verified PASS. Live at https://wgs-studio.vercel.app (backend: https://wgs-backend-production.up.railway.app).

All six phases are done. Since Phase 6, on top of the original scope: a Supabase-Auth login screen gating the whole app + RLS on `brand_kit`/`memory`/`image_cache`; `memory`/`brand_kit` migrated off local disk to real Supabase reads/writes (survives a Railway restart, verified); a citation/grounding bug fix so `requires_citation: true` taxonomy topics stay grounded in the accepted angle instead of drifting to unrelated content (logbook #14/#15) — deployed and verified live in production; both Vercel and Railway now auto-deploy on push, scoped correctly (`watchPatterns`) and health-check-gated, after a real outage (logbook #20) got root-caused and fixed rather than just contained (logbook #23); `brand_kit`'s RLS was found wide open (`authenticated_full_access` — any authenticated session, full read/write) and tightened to service-role-only, with a database-level `audit_log` added for both `brand_kit` and `memory` (logbook #34); a real export-confirmation event built for the first time — `memory` gained `caption`/`slides`/`exported_at`/`voice_trained_at`, the voice-compounding mechanism (blueprint Section 4) actually fires now via an explicit opt-in toggle, and the masthead counter (stuck at `NO. 01` since Phase 6, since nothing had ever flipped a record to `exported`) is fixed as a direct consequence (logbook #35); `refine_post` compounding a `critique_post` false-positive into unwanted slide-count drift on fixed-slide-count formats, root-caused and fixed (logbook #29/#37); and one closed non-issue — the hero-image cache's low hit rate (logbook #13) was investigated and found no longer to be a real gap, closed rather than carried forward as open work (logbook #36). Full detail, plus every other post-deploy fix, is in `docs/logbook.md` — that's the source of truth for "what's actually happened," not this section.

*(Update this section whenever status materially changes — a phase completes, or a significant post-deploy fix lands. Keep it a short orientation summary; put the real detail in the logbook.)*

---

## Phase-gating rule — non-negotiable

After finishing any phase: invoke an independent check against that phase's "Done when" criteria (see note below on `phase-verifier`), report pass/fail per criterion with concrete evidence, then **stop**. Do not begin the next phase without explicit confirmation, even if verification passes.

**Known environment note:** the custom `phase-verifier` subagent (`.claude/agents/phase-verifier.md`) is not recognized by this session's Agent tool — only built-in agent types are available. Use `general-purpose` instead, with the exact phase-verifier persona and instructions pasted in. Same independent, skeptical, read-only check — just a different dispatch path. Don't keep re-attempting the custom subagent; this is a confirmed limitation, not a fixable bug.

---

## Logbook discipline — non-negotiable

Every time a change is made to fix a reported issue (a bug, a broken deploy, an
unexpected production failure — anything beyond routine new-feature build-out),
add an entry to `docs/logbook.md` in the same session, before considering the fix
done. Entry shape (match the existing ones): symptom, investigation/root cause,
fix, and whether it deviates from `blueprint.md`/`implementation-guide.md` (call
this out explicitly, even if the answer is "no deviation" — that's still useful
signal). Dead-end attempts that didn't work are worth keeping too, so they aren't
retried blind later (see logbook #12 for the pattern).

**Why:** once the project is in day-to-day use, the logbook becomes a primary
source (alongside the blueprint/implementation-guide) for writing a final system
architecture document — it needs to be complete as we go, not reconstructed from
memory or git archaeology after the fact.

This does not apply to routine forward build-out of a phase's planned scope —
just to anything that came up as a problem and got fixed.

---

## Locked decisions — don't re-litigate these

- **Brand:** Women's Growth Society, masthead short form `WGS`, handle `@womensgrowthsociety`
- **Fonts:** Archivo Black (structural) + Alex Brush (script accent, one word/phrase only) + Inter (body/labels) — all free Google Fonts
- **Three duotone moods:** wisdom (violet) / bold (terracotta) / celebratory (gold) — see `WGS_BRAND_KIT` in Section 4/6 of the docs for exact hex values
- **Voice:** two registers (poetic, direct), resolved deterministically per-post via `APPROACH_REGISTER` — never guessed by the model
- **Models:** Claude Haiku 4.5 (cheap tier) + Claude Sonnet 5 (strong tier) for the app's own generation; GPT Image 2 for hero images
- **Rendering:** Satori via `@vercel/og`, on the frontend (Next.js route) — no headless browser, ever
- **Stack:** Next.js/React/Vercel (frontend) · FastAPI/Python/Railway (backend) · Supabase (DB + storage)

---

## Environment

- `backend/.env` and `frontend/.env.local` exist locally with real API keys already filled in — **do not recreate them or generate fresh `.env.example` placeholders that overwrite real values.**
- Both are correctly gitignored — verify with `git status` before any commit that they don't appear as staged.
- `IMAGE_QUALITY=low` — the medium→low experiment ran: duotoned output is visually indistinguishable, and low cut worst-case `/generate` latency roughly in half-to-third (100+s outliers down to a consistent ~20-32s) plus ~8x lower image cost. Switched on both Railway and local `.env`.
- **Frontend must build with `--webpack`, not Turbopack** (`frontend/package.json`'s `build` script is `next build --webpack`) — Next 16's default Turbopack production build silently skips the "Collecting build traces" step for this project, so the compiled `@vercel/og` binary Next's internal og module needs at runtime never makes it into the deployed Vercel serverless function. Every `/api/render` call 500'd in production until this was found (build succeeded and worked fine with `next dev`/local `next start` either way — this only ever showed up as a deployed-on-Vercel failure). Don't switch this back to Turbopack without re-verifying `/api/render` in production first.
- **Git integration is connected on both platforms and both are now trusted.** #20's outage (a docs-only push crashed the live service — `uvicorn: command not found` despite installing cleanly) was root-caused in #23, not just contained: `uv sync` was intermittently ignoring the pre-activated `/opt/venv` and installing into a separate `/app/.venv` instead (visible in build logs as a `VIRTUAL_ENV=/opt/venv does not match...` warning, present on every crash, absent on every success). Fixed by pinning `UV_PROJECT_ENVIRONMENT=/opt/venv` as a Railway service variable, forcing `uv` to always target the activated venv — verified by the warning's absence on the next build, not just a green deployment. `build.watchPatterns: ["/backend/**"]` in `railway.json` also means non-backend pushes (like this one) no longer trigger a Railway build attempt at all (confirmed: `SKIPPED`). Railway also has `NIXPACKS_UV_VERSION` pinned (currently `0.4.30`) for the same reason — without it, Nixpacks resolves `uv`'s own version via a live external lookup that can transiently fail. If a manual `railway up` is ever needed, run it from the **repo root**, not `backend/` — Root Directory being set for the git integration means a CLI upload from inside `backend/` now double-nests and fails. Full detail: `DEPLOY.md` §0, logbook #17-#23.
- The health-check gate (`deploy.healthcheckPath`/`healthcheckTimeout` in `railway.json`, added in #21) stays regardless — it's cheap insurance, not a sign auto-deploy is still untrusted.

---

## Working notes

- Bypass permissions mode is unreliable in this VS Code extension session (known extension bug) — expect occasional Bash prompts even with it enabled; this is fine, not worth fighting.
- Run `/clear` when starting a new phase, `/compact` when continuing deep into one — keeps context cost down. This file plus the two docs are enough to re-orient after either.
