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
- ✅ Phase 6 (Deployment) — complete, verified PASS. Live at https://wgs-studio.vercel.app (backend: https://wgs-backend-production.up.railway.app). Also added beyond the original Phase 6 spec: a Supabase-Auth login screen gating the whole app, and RLS policies locking brand_kit/memory/image_cache to the authenticated role.

*(Update this section at the end of every phase — check off the completed one and move the ⏳ marker to the next.)*

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

---

## Working notes

- Bypass permissions mode is unreliable in this VS Code extension session (known extension bug) — expect occasional Bash prompts even with it enabled; this is fine, not worth fighting.
- Run `/clear` when starting a new phase, `/compact` when continuing deep into one — keeps context cost down. This file plus the two docs are enough to re-orient after either.
