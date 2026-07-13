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

---

## Working notes

- Bypass permissions mode is unreliable in this VS Code extension session (known extension bug) — expect occasional Bash prompts even with it enabled; this is fine, not worth fighting.
- Run `/clear` when starting a new phase, `/compact` when continuing deep into one — keeps context cost down. This file plus the two docs are enough to re-orient after either.
