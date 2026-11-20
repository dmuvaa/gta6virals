/** Site-wide content. Keep plan limits in sync with backend/gta_clipper/config.py. */
export const BRAND = process.env.NEXT_PUBLIC_BRAND_NAME || "Hypecut";
export const TAGLINE = "Turn 12-hour streams into hundreds of clips, in minutes.";
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(/\/$/, "");
export const SUPPORT_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "support@example.com";
export const COMPANY = process.env.NEXT_PUBLIC_COMPANY_NAME || BRAND;

export type PlanKey = "free" | "creator" | "pro";
export type Plan = {
  key: PlanKey; name: string; price: number; hours: number; exports: number; captions: boolean;
  watermark: boolean; maxVideoHours: number; blurb: string; features: string[]; priceEnv?: string;
};

export const PLANS: Plan[] = [
  { key: "free", name: "Free", price: 0, hours: 3, exports: 10, captions: false, watermark: true, maxVideoHours: 4,
    blurb: "Try the full review workflow on a few streams.",
    features: ["3 hours of video per month", "10 HD clip exports", "All 9:16 and 16:9 layouts", "Webcam auto-detect", "Small watermark on exports"] },
  { key: "creator", name: "Creator", price: 19, hours: 60, exports: 300, captions: true, watermark: false, maxVideoHours: 24,
    blurb: "For clippers posting every day.",
    features: ["60 hours of video per month", "300 HD clip exports", "Burned-in captions", "No watermark", "Streams up to 24 hours", "Download all as .zip"] },
  { key: "pro", name: "Pro", price: 49, hours: 300, exports: 2000, captions: true, watermark: false, maxVideoHours: 24,
    blurb: "For full-time clippers and small teams.",
    features: ["300 hours of video per month", "2,000 HD clip exports", "Everything in Creator", "Priority processing", "Email support"] },
];

export const PADDLE = {
  env: process.env.NEXT_PUBLIC_PADDLE_ENV || "sandbox",
  token: process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN || "",
  prices: {
    creator: process.env.NEXT_PUBLIC_PADDLE_PRICE_CREATOR || "",
    pro: process.env.NEXT_PUBLIC_PADDLE_PRICE_PRO || "",
  } as Record<string, string>,
};
export const billingEnabled = () => Boolean(PADDLE.token && PADDLE.prices.creator && PADDLE.prices.pro);

export const FAQ: [string, string][] = [
  ["What does it do?", "Paste a YouTube or Twitch link to a stream or video. We scan the whole thing, even 24-hour streams, and line up every moment with action: big reactions, chaos, chases, shootouts. You play through them, keep the good ones, and download them as ready-to-post clips."],
  ["How fast is it?", "Scanning works from the audio over many parallel connections, so a 12-hour stream is usually ready to review in a few minutes. Previews load in under a second, and kept clips are made in HD in seconds."],
  ["How many clips will I get?", "About 13 moments per hour of stream, 15 to 45 seconds each. A 24-hour stream gives around 300 moments. You decide which ones become clips."],
  ["Which formats can I export?", "9:16 with the streamer's webcam on top and gameplay below (the webcam is found automatically), 9:16 with a blurred background, 9:16 center crop, or the original 16:9. Paid plans add burned-in captions with word-by-word highlighting."],
  ["Is it only for GTA VI?", "It's tuned for GTA VI streams (webcam layouts, gameplay detection), but it works on any gaming or IRL stream on YouTube or Twitch."],
  ["Can I use it for clipping campaigns?", "Yes. Many streamers pay clippers per view through clipping campaigns. Always follow each campaign's rules, and only clip content you have permission to use."],
  ["Can I cancel anytime?", "Yes. Plans are monthly and you can cancel from your account page. You keep your plan until the end of the billing period."],
  ["Do you store my videos?", "Projects and clips are stored temporarily so you can review and download them, then deleted automatically. You can also delete a project or your whole account at any time."],
];

export const fmtTime = (s: number) => {
  s = Math.max(0, Math.round(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(x).padStart(2, "0")}` : `${m}:${String(x).padStart(2, "0")}`;
};
