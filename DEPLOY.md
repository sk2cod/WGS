# Deploying WGS Content Studio

One GitHub repo, two deploy targets (Railway for `backend/`, Vercel for `frontend/`), one Supabase project.

**Status: push to `main` and both platforms auto-deploy, scoped and health-gated.** Both are connected via native GitHub integration. Railway had a real outage during setup (logbook #20 — a build succeeded but crashed at runtime, and traffic cut over before anyone noticed) that got root-caused and fixed (logbook #23), not just papered over: `uv sync` was intermittently ignoring the pre-activated `/opt/venv` and installing into a separate `/app/.venv` instead, leaving `/opt/venv` (where `PATH` pointed) without `uvicorn`. Fixed by pinning `UV_PROJECT_ENVIRONMENT=/opt/venv` as a service variable, forcing determinism. Two more safety nets stay on regardless (logbook #21): `build.watchPatterns` scopes Railway rebuilds to actual backend changes, and a health-check gate means a bad deployment can no longer cut over traffic even if something new goes wrong — it'll fail safe, keeping the last good deployment live, the same way Vercel already behaves.

## 0. Git integration setup

- **Vercel**: requires the "Vercel" GitHub App to be authorized on the GitHub account first — a one-time browser step (GitHub → Settings → Installations → configure the Vercel app → grant access to the repo, or via the Vercel dashboard's own "Connect Git Repository" flow). There's no CLI path for this authorization; `vercel git connect` fails outright until it's done. Once authorized, **Root Directory must be set to `frontend`** in the Vercel dashboard (Settings → General) — a project originally linked via CLI from inside `frontend/` will show Root Directory `.`, which is wrong once GitHub is the source.
- **Railway**: `railway service source connect --repo <owner>/<repo> --branch main --service wgs-backend` works via CLI, no browser step needed. **Root Directory must be set to `backend`** (Service → Settings → Source) — connecting the source alone doesn't set this, and Railway's build will fail immediately (`Railpack could not determine how to build the app`) against the bare repo root of a monorepo.
- **Railway service variables, both required, neither self-updating:**
  - `NIXPACKS_UV_VERSION` (currently `0.4.30`) — without it, Nixpacks resolves `uv`'s own version via a live external lookup at build time (`astral-sh/uv`'s GitHub releases) that can transiently fail, producing `pip install uv==` (empty) and a hard build failure.
  - `UV_PROJECT_ENVIRONMENT=/opt/venv` — without it, `uv sync` intermittently creates a separate venv at `/app/.venv` instead of using the one Nixpacks already activated at `/opt/venv` (where `PATH` and the start command expect it), producing a container that builds successfully but crashes with `uvicorn: command not found` (logbook #20, root-caused and fixed in #23). Verify this fix is holding by checking build logs for the absence of the warning `VIRTUAL_ENV=/opt/venv does not match the project environment path .venv` — its presence means the fix has regressed.
  - Both are plain Railway service variables (Settings → Variables), not `railway.json` fields — confirmed Railway exposes all service variables during the Nixpacks build step, not just at runtime.
- `railway.json`'s `build.watchPatterns: ["/backend/**"]` scopes rebuild triggers to backend changes only — confirmed via Railway's live schema and docs that patterns are **repo-root-relative even with Root Directory set**, so this needed the leading slash and full `backend/` prefix, not a bare `backend/**` assumed relative to the service root.
- **Vercel has no equivalent scoping today.** There's no `vercel.json`/`ignoreCommand` in `frontend/` (confirmed: none exists anywhere in the repo), so every push to `main` — including backend-only or docs-only changes — triggers a full Vercel rebuild, not just pushes that touch `frontend/`. This is documented as current fact, not queued as a fix: Railway's `watchPatterns` exists because non-backend rebuilds were an active production risk (#20/#23 — a crashing backend build cutting over traffic); Vercel rebuilding on every push doesn't carry that same risk profile, so scoping it hasn't been treated as a priority.
- `railway.json`'s `deploy.healthcheckPath: "/topics"` + `healthcheckTimeout: 60` makes Railway verify a new deployment actually responds before routing production traffic to it — this is what prevented a second outage (logbook #22) when the `uvicorn` bug recurred once more before being root-caused.
- **Important gotcha, affects manual deploys too:** once Root Directory is set to `backend` on the Railway service, `railway up` **must be run from the repo root**, not from inside `backend/` — running it from `backend/` now uploads that folder as the app root, and Railway then looks for a doubly-nested `backend/backend/...` that doesn't exist, failing with `Failed to read app source directory`. This changed the moment the git integration was connected; it wasn't true before.
- **Verifying either integration is actually live** (don't trust dashboard status text alone): push a commit, then check `vercel ls` / `railway deployment list --service wgs-backend` for a new deployment appearing within seconds, and confirm it via commit-hash match (`vercel inspect <url>` / `railway status --json | grep commitHash`) rather than just "a deployment happened."

## 1. Backend — Railway

1. `railway login`
2. `railway init` (or `railway link` if a project already exists) to create the service.
3. Set env vars (Railway dashboard → service → Variables, or `railway variables --set KEY=VALUE`) from `backend/.env.example` — real values come from `backend/.env` locally, Anthropic/OpenAI/Supabase dashboards. Don't forget `NIXPACKS_UV_VERSION` and `UV_PROJECT_ENVIRONMENT` (see §0).
   - Leave `FRONTEND_ORIGIN` as `http://localhost:3000` for the first deploy; it gets updated in step 3 below once the Vercel URL exists.
4. **Deploy with `railway up` from the repo root** (see §0's gotcha — not from `backend/`, if Root Directory is configured). Start command comes from `backend/railway.json` (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
5. `railway domain` to generate the public URL (or copy it from the dashboard). This is `NEXT_PUBLIC_API_URL` for the frontend.

## 2. Frontend — Vercel

1. `vercel login`
2. From `frontend/`: `vercel link` (create/select project — named `wgs`, or a fallback if taken).
3. Set env vars (`vercel env add`, or the dashboard) from `frontend/.env.local.example`:
   - `NEXT_PUBLIC_API_URL` = the Railway URL from step 1.5.
   - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` = from the Supabase project settings.
4. `vercel --prod` to deploy manually, or rely on Vercel's auto-deploy on push (confirmed reliable so far — see status note above). Note the resulting `*.vercel.app` URL.

## 3. Backend redeploy — real CORS origin

1. Update `FRONTEND_ORIGIN` on Railway to the Vercel URL from step 2.4.
2. Redeploy so `CORSMiddleware` in `app/main.py` picks up the real origin — `railway up` from the repo root (see §0).

## 4. Supabase

1. Create a project at supabase.com (or `supabase projects create`).
2. Run `backend/app/db/schema.sql` against it (SQL editor, or a direct `psql`/`psycopg` connection using `SUPABASE_DB_URL`) — creates `brand_kit`, `memory`, `image_cache`, and `audit_log` tables, the `heroes` Storage bucket, and enables RLS on all four tables. `authenticated` has zero access — the original `authenticated_full_access` policy (`FOR ALL`/`using(true)`/`with check(true)`, wide open to any authenticated session) was found and revoked in logbook #34 — and `anon` has none either; only the backend's `service_role` key (a role property that bypasses RLS regardless) can read or write. `memory` also carries `caption`, `slides`, `exported_at`, and `voice_trained_at` (added in logbook #35, for the export-confirmation event).
3. Copy the project URL + `service_role` key into Railway's env vars (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL`), and the project URL + `anon` key into Vercel's (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`).
4. Create one auth user (dashboard → Authentication → Add user, email confirmed) — single-creator app, no signup flow. This is the login used at `/login`; every other route redirects there until signed in (`components/AuthGate.tsx`).

## Verifying

Open the Vercel URL on a phone, sign in with the one Supabase auth user's credentials, generate a post end-to-end (pick → generate → editor → export), and confirm the network calls hit the Railway domain and succeed.

## Notes on the Vercel alias

`vercel alias set` only binds a domain to one specific deployment — it does not follow future deploys. To get a clean URL that auto-tracks production the way the default `<project>.vercel.app` domain does, register it as a project domain instead: `vercel domains add <domain> <project>`. Also: don't remove Vercel's auto-assigned default `.vercel.app` domain (e.g. `wgs-two.vercel.app`) even if nothing in the codebase references it directly — it's baked into the project's dashboard metadata as the canonical default, and removing it breaks the dashboard's production-domain display without actually taking anything down (see `docs/logbook.md` #10).
