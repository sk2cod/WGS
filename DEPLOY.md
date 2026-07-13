# Deploying WGS Content Studio

One GitHub repo, two deploy targets (Railway for `backend/`, Vercel for `frontend/`), one Supabase project. Deploy backend first — the frontend needs its URL; then redeploy the backend once more after the frontend exists, so CORS can point at the real Vercel domain.

## 1. Backend — Railway

1. `railway login`
2. From `backend/`: `railway init` (or `railway link` if a project already exists) to create the service.
3. Set env vars (Railway dashboard → service → Variables, or `railway variables --set KEY=VALUE`) from `backend/.env.example` — real values come from `backend/.env` locally, Anthropic/OpenAI/Supabase dashboards.
   - Leave `FRONTEND_ORIGIN` as `http://localhost:3000` for the first deploy; it gets updated in step 3 below once the Vercel URL exists.
4. `railway up` to deploy. Start command comes from `backend/railway.json` (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`); build uses Nixpacks, which picks up `uv.lock` automatically.
5. `railway domain` to generate the public URL (or copy it from the dashboard). This is `NEXT_PUBLIC_API_URL` for the frontend.

## 2. Frontend — Vercel

1. `vercel login`
2. From `frontend/`: `vercel link` (create/select project — named `wgs`, or a fallback if taken).
3. Set env vars (`vercel env add`, or the dashboard) from `frontend/.env.local.example`:
   - `NEXT_PUBLIC_API_URL` = the Railway URL from step 1.5.
   - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` = from the Supabase project settings.
4. `vercel --prod` to deploy. Note the resulting `*.vercel.app` URL.

## 3. Backend redeploy — real CORS origin

1. Update `FRONTEND_ORIGIN` on Railway to the Vercel URL from step 2.4.
2. `railway up` again (or trigger via dashboard) so `CORSMiddleware` in `app/main.py` picks up the real origin.

## 4. Supabase

1. Create a project at supabase.com (or `supabase projects create`).
2. Run `backend/app/db/schema.sql` against it (SQL editor, or `supabase db push`) — creates `brand_kit`, `memory`, `image_cache` tables and the `heroes` Storage bucket.
3. Copy the project URL + `service_role` key into Railway's env vars (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL`), and the project URL + `anon` key into Vercel's (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`).
4. Create one auth user (dashboard → Authentication → Add user) — single-creator app, no signup flow.

## Verifying

Open the Vercel URL on a phone, generate a post end-to-end (pick → generate → editor → export), and confirm the network calls hit the Railway domain and succeed.
