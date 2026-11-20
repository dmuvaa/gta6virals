# Hypecut

A web app that turns long YouTube and Twitch streams into hundreds of reviewable moments,
then into ready-to-post clips. It includes a marketing site (landing, pricing, FAQ, legal),
accounts, a dashboard, the review workspace, plan limits, and Paddle billing.

## Pages
| Path | What it is |
|---|---|
| `/` | Landing page: hero, features, how it works, pricing, FAQ |
| `/pricing`, `/faq` | Plans with a comparison table; full FAQ |
| `/legal/terms`, `/legal/privacy`, `/legal/copyright` | Legal drafts (have a lawyer review them) |
| `/signup`, `/login` | Accounts (email + password, CSRF-protected) |
| `/app` | Dashboard: usage meters and projects |
| `/app/new` | New project: link preview, layout, captions, scan range |
| `/app/p/<id>` | Review workspace: keep or discard moments, kept clips, .zip download |
| `/app/account` | Plan and usage, manage billing, password, delete account |
| `/robots.txt`, `/sitemap.xml` | SEO. Every page also has meta, Open Graph and Twitter tags; the landing, pricing and FAQ pages carry JSON-LD |

## Plans
Defined in `gta_clipper/config.py` (`PLANS`):
- **Free:** 3 h/month, 10 exports, watermark, no captions, 4 h max per video.
- **Creator:** $19, 60 h/month, 300 exports, captions, no watermark.
- **Pro:** $49, 300 h/month, 2,000 exports.

Hours are charged when a scan starts; exports are charged when a moment is kept.

## Billing (Paddle)
Paddle is the merchant of record: it runs checkout, charges customers, handles sales tax and
VAT, and pays you out. Billing stays off, and paid plans show "opening soon", until these
variables are set:

1. In Paddle (start in the **sandbox**), create a product with two monthly prices ($19 and $49).
   Put their IDs in `PADDLE_PRICE_CREATOR` and `PADDLE_PRICE_PRO`.
2. **Developer tools → Authentication:** create a client-side token (`PADDLE_CLIENT_TOKEN`)
   and an API key (`PADDLE_API_KEY`).
3. **Developer tools → Notifications:** add a destination `https://YOUR-DOMAIN/billing/webhook`
   for the `subscription.*` events. Copy its secret key into `PADDLE_WEBHOOK_SECRET`.
4. Add your domain to Paddle's approved domains. When you go live, switch to production keys
   and set `PADDLE_ENV=production`.

All settings are listed in `.env.example`.

## Run it

```bash
./run.sh
```

Then open http://localhost:8765. Requires Python 3.10+ and ffmpeg (`brew install ffmpeg`).
Captions also need whisper.cpp (`brew install whisper-cpp`) and the speech model in
`models/` (`ggml-small.en-q5_1.bin` from the whisper.cpp model repo on Hugging Face).

Command line instead of the UI:

```bash
.venv/bin/python -m gta_clipper "https://www.twitch.tv/videos/123" --format vertical_facecam
```

## How it works

1. **Scan the whole video's audio, fast.** For YouTube and Twitch the app pulls the bytes
   directly over 12 parallel connections instead of yt-dlp's time-range downloader, which
   streams at about playback speed. On YouTube the MP4 `sidx` index maps time to byte
   ranges; on Twitch the HLS playlist does. A whole 11.7-hour stream's audio takes ~55 s.
2. **Find moments.** Every half-second is scored on:
   - loudness above the local baseline
   - sudden jumps in volume (reactions)
   - **activity:** how many sound events happen per ~8 s (chases, gunfights, chaos)
   - YouTube's "Most replayed" data, when the video has it

   Each moment grows from its peak for as long as the action keeps going (15–45 s), plus a
   short lead-in.
3. **Review.** Each moment has a 360p preview (~3 MB, ~0.4 s to fetch). Previews are made in
   the background, best moments first, and each one gets a gameplay check:
   - **static screen:** almost no motion
   - **not gameplay:** a big face fills the frame, or the streamer's webcam overlay border
     is missing

   Flagged moments are hidden by default, one click away. Keys: `K` keep, `X` discard,
   `←`/`→` move, `Space` play/pause, `[` `]` start −/+2 s, `;` `'` end −/+2 s.
4. **Make kept clips** in HD (~4 s fetch on YouTube) with exact timing from the index.
   Optional captions are transcribed locally with whisper.cpp, shown 3 words at a time in
   bold uppercase with the spoken word highlighted. Layouts:
   - `vertical_facecam`: webcam on top, gameplay below. The webcam is auto-detected (the same
     small face on the same pixels in moments 20+ minutes apart, box snapped to the overlay
     border), or you can draw the box yourself.
   - `vertical_blur`: full frame over a blurred 9:16 fill
   - `vertical_crop`: center crop
   - `horizontal`: original 16:9

   "Download all (.zip)" bundles every kept clip.

Other sites supported by yt-dlp fall back to the slower path: a low-res copy for analysis,
plus motion scoring.

In the UI each clip can be re-trimmed (±2 s or exact times), switched to another format, or
downloaded.

## Limits / notes

- Twitch is slower than YouTube: it has no low-bitrate audio-only stream, and 1080p60 sections are large.
- The gameplay check is a hint, not a filter: some menus and camera breaks get through, and the occasional real moment gets flagged.
- Live chat isn't used: YouTube serves chat replay far too slowly for long streams, and Twitch's chat API requires an integrity token.
- Sub-only, private, or age-restricted videos can't be downloaded.
- Live streams: use the VOD once the stream ends.
- Only clip content you have the rights to post (your own streams, or with the creator's
  permission). Don't use Rockstar/Take-Two logos or the "GTA" mark in your product branding.
- Output and downloads live in `work/`. Delete job folders there to free disk space.
