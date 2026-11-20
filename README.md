# Hypecut

Turns long YouTube and Twitch streams into hundreds of reviewable moments, then into
ready-to-post clips.

```
web/        Next.js site: marketing, auth (Supabase), dashboard, review workspace, Paddle checkout
backend/    Python: API (Flask) + worker (scan, previews, renders) on a Supabase job queue
supabase/   Database schema (run migrations/0001_init.sql in Supabase → SQL Editor)
```

## How it fits together
- **Supabase:** logins, plus Postgres for profiles, usage, projects, moments, and a `tasks`
  job queue. The browser reads only its own rows (RLS). The backend uses the secret key.
- **API:** verifies the user's Supabase token, enforces plan limits, queues tasks, signs
  file links, and receives Paddle webhooks.
- **Worker:** claims tasks (`claim_task()`, safe across many workers). It scans audio over
  direct parallel HTTP, picks moments, makes previews, flags non-gameplay, detects the webcam,
  and renders kept clips with captions and watermark.
- **Files:** stored in Cloudflare R2 in production (local disk in development) and served
  through short-lived signed links.

## Run locally
1. Run `supabase/migrations/0001_init.sql` in your Supabase project.
2. In Supabase → Authentication → URL Configuration, set Site URL to `http://localhost:3000`
   and add the redirect `http://localhost:3000/auth/callback`.
3. Fill in `.env` (backend) and `web/.env.local` (public values only). See `.env.example`.
4. Start the three processes:

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
cd backend && .venv/bin/python -m gta_clipper api --port 8765
```

```bash
cd backend && .venv/bin/python -m gta_clipper worker
```

```bash
cd web && npm install && npm run dev
```

Requirements: Python 3.10+, Node 20+, and ffmpeg. Captions also need whisper.cpp
(`brew install whisper-cpp`) and a model in `backend/models/`.

## Deploy
**Website → Vercel:** import the repo, set **Root Directory** to `web`, and add the
`NEXT_PUBLIC_…` variables from `.env.example`. They're baked in at build time, so redeploy
after changing them.

**API + worker → Render:** Dashboard → **New → Blueprint** → this repo. `render.yaml`
creates `hypecut-api` (Docker) and `hypecut-worker` (Docker, background worker), plus a
shared `hypecut-backend` env group. Then:
- **Cloudflare R2 is required in production:** create a bucket and an API token and set the
  `R2_*` variables.
- Set `WEB_ORIGINS` and `API_URL` on the API, and `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_SITE_URL`
  on the website.
- In Supabase Auth, add the production Site URL and `https://YOUR-SITE/auth/callback`.
- **Paddle:** create the $19 and $49 monthly prices, set the client token and price IDs (web),
  and the API key, webhook secret and price IDs (backend). Point a webhook at
  `https://YOUR-API/api/billing/webhook` for `subscription.*` events.

## Plans
Defined in `backend/gta_clipper/config.py` and mirrored in `web/src/lib/site.ts`:
- **Free:** 3 h/month, 10 exports, watermark, 4 h per video.
- **Creator:** $19, 60 h/month, 300 exports, captions.
- **Pro:** $49, 300 h/month, 2,000 exports.
