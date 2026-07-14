# Deploying WGS Content Studio

One GitHub repo, two deploy targets (Railway for `backend/`, Vercel for `frontend/`), one Supabase project.

**Current workflow: push to `main` and both platforms deploy automatically.** Both are connected via native GitHub integration (set up per `docs/logbook.md` #17-#19) — there is no manual deploy step for routine changes. The sections below describe the one-time setup (for a fresh environment, or if you ever need to reconnect either integration) and the manual-override commands, kept for reference.

## 0. One-time git integration setup (already done for this project)

- **Vercel**: requires the "Vercel" GitHub App to be authorized on the GitHub account first — a one-time browser step (GitHub → Settings → Installations → configure the Vercel app → grant access to the repo, or via the Vercel dashboard's own "Connect Git Repository" flow). There's no CLI path for this authorization; `vercel git connect` fails outright until it's done. Once authorized, **Root Directory must be set to `frontend`** in the Vercel dashboard (Settings → General) — a project originally linked via CLI from inside `frontend/` will show Root Directory `.`, which is wrong once GitHub is the source.
- **Railway**: `railway service source connect --repo <owner>/<repo> --branch main --service wgs-backend` works via CLI, no browser step needed. **Root Directory must be set to `backend`** (Service → Settings → Source) — connecting the source alone doesn't set this, and Railway's build will fail immediately (`Railpack could not determine how to build the app`) against the bare repo root of a monorepo.
- **Railway also needs `NIXPACKS_UV_VERSION` pinned as a service variable** (currently `0.4.30`) — without it, Nixpacks resolves `uv`'s version via a live external lookup at build time (`astral-sh/uv`'s GitHub releases) instead of anything in this repo, and that lookup can transiently fail, producing `pip install uv==` (empty) and a hard build failure. Pinning it removes the external dependency. If `uv` ever needs upgrading, this is the variable to bump — it will not update itself.
- **Verifying either integration is actually live** (don't trust dashboard status text alone): push an empty commit (`git commit --allow-empty -m "test" && git push origin main`), then check `vercel ls` / `railway deployment list --service wgs-backend` for a new deployment appearing within seconds, and confirm it via commit-hash match (`vercel inspect <url>` / `railway status --json | grep commitHash`) rather than just "a deployment happened."

## 1. Backend — Railway (manual override / fresh setup)

1. `railway login`
2. From `backend/`: `railway init` (or `railway link` if a project already exists) to create the service.
3. Set env vars (Railway dashboard → service → Variables, or `railway variables --set KEY=VALUE`) from `backend/.env.example` — real values come from `backend/.env` locally, Anthropic/OpenAI/Supabase dashboards. Don't forget `NIXPACKS_UV_VERSION` (see §0).
   - Leave `FRONTEND_ORIGIN` as `http://localhost:3000` for the first deploy; it gets updated in step 3 below once the Vercel URL exists.
4. `railway up` to deploy manually (or connect GitHub per §0 for auto-deploy going forward). Start command comes from `backend/railway.json` (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
5. `railway domain` to generate the public URL (or copy it from the dashboard). This is `NEXT_PUBLIC_API_URL` for the frontend.

## 2. Frontend — Vercel (manual override / fresh setup)

1. `vercel login`
2. From `frontend/`: `vercel link` (create/select project — named `wgs`, or a fallback if taken).
3. Set env vars (`vercel env add`, or the dashboard) from `frontend/.env.local.example`:
   - `NEXT_PUBLIC_API_URL` = the Railway URL from step 1.5.
   - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` = from the Supabase project settings.
4. `vercel --prod` to deploy manually (or connect GitHub per §0 for auto-deploy going forward). Note the resulting `*.vercel.app` URL.

## 3. Backend redeploy — real CORS origin

1. Update `FRONTEND_ORIGIN` on Railway to the Vercel URL from step 2.4.
2. Redeploy so `CORSMiddleware` in `app/main.py` picks up the real origin — either push to `main` (auto-deploy) or `railway up` manually.

## 4. Supabase

1. Create a project at supabase.com (or `supabase projects create`).
2. Run `backend/app/db/schema.sql` against it (SQL editor, or a direct `psql`/`psycopg` connection using `SUPABASE_DB_URL`) — creates `brand_kit`, `memory`, `image_cache` tables, the `heroes` Storage bucket, and enables RLS on all three tables (full access for `authenticated`, none for `anon` — the backend's `service_role` key bypasses RLS regardless).
3. Copy the project URL + `service_role` key into Railway's env vars (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL`), and the project URL + `anon` key into Vercel's (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`).
4. Create one auth user (dashboard → Authentication → Add user, email confirmed) — single-creator app, no signup flow. This is the login used at `/login`; every other route redirects there until signed in (`components/AuthGate.tsx`).

## Verifying

Open the Vercel URL on a phone, sign in with the one Supabase auth user's credentials, generate a post end-to-end (pick → generate → editor → export), and confirm the network calls hit the Railway domain and succeed.

## Notes on the Vercel alias

`vercel alias set` only binds a domain to one specific deployment — it does not follow future deploys. To get a clean URL that auto-tracks production the way the default `<project>.vercel.app` domain does, register it as a project domain instead: `vercel domains add <domain> <project>`. Also: don't remove Vercel's auto-assigned default `.vercel.app` domain (e.g. `wgs-two.vercel.app`) even if nothing in the codebase references it directly — it's baked into the project's dashboard metadata as the canonical default, and removing it breaks the dashboard's production-domain display without actually taking anything down (see `docs/logbook.md` #10).
