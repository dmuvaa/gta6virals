/** Content for the SEO pages: related links and the /tools/* keyword pages. */
import { BRAND } from "./site";

export const RELATED = {
  hub: { href: "/gta-6-clips", title: "GTA 6 clip maker", text: "The complete guide to turning GTA 6 streams into viral clips." },
  twitch: { href: "/tools/twitch-vod-clipper", title: "Twitch VOD clipper", text: "Find every highlight in a long Twitch VOD in minutes." },
  youtube: { href: "/tools/youtube-stream-clipper", title: "YouTube stream clipper", text: "Clip YouTube live replays and long videos, whole thing at once." },
  vertical: { href: "/tools/vertical-video-converter", title: "Stream to 9:16 converter", text: "Webcam-on-top layouts for TikTok, Shorts and Reels." },
  captions: { href: "/tools/auto-captions-for-gaming-clips", title: "Auto captions for gaming clips", text: "Bold, word-by-word captions that keep viewers watching." },
  campaigns: { href: "/guides/gta-6-clipping-campaigns", title: "GTA 6 clipping campaigns", text: "How paid clipping works, pools vs CPM, and how to win." },
  pricing: { href: "/pricing", title: "Pricing", text: "Free plan to start, Creator and Pro for daily clippers." },
} as const;
export type RelatedKey = keyof typeof RELATED;

export type ToolPage = {
  slug: string; title: string; metaTitle: string; description: string; eyebrow: string; h1: string; lead: string;
  benefits: [string, string][]; steps: [string, string][]; body: { h: string; p: string[] }[];
  faq: [string, string][]; related: RelatedKey[]; cta: [string, string];
};

export const TOOLS: ToolPage[] = [
  {
    slug: "twitch-vod-clipper",
    title: "Twitch VOD clipper",
    metaTitle: "Twitch VOD Clipper: Find Every Highlight in Long Streams",
    description: `Clip long Twitch VODs in minutes. ${BRAND} scans the whole stream, lines up every moment with action, and exports 9:16 clips with the webcam on top.`,
    eyebrow: "Twitch VOD clipper",
    h1: "Clip an entire Twitch VOD without scrubbing through it",
    lead: `Paste a Twitch VOD link. ${BRAND} scans the full stream, even a 13-hour marathon, and lines up every moment worth posting, best first.`,
    benefits: [
      ["Whole VOD, one pass", "No more watching at 2× speed. The full stream is scanned in one go and every busy stretch becomes a reviewable moment."],
      ["Webcam layout built in", "The streamer's camera is found automatically and placed above the gameplay for vertical platforms."],
      ["Only HD what you keep", "Moments preview instantly at low resolution; only the ones you keep are fetched and rendered in 1080p."],
    ],
    steps: [
      ["Copy the VOD link", "Open the past broadcast on Twitch and copy its URL (twitch.tv/videos/…). Twitch clips work too."],
      ["Paste it into a new project", "Pick a layout and optionally a time range. The scan starts right away."],
      ["Review and keep", "Play each moment, press K to keep or X to skip, nudge the start and end if needed."],
      ["Download and post", "Kept clips render in HD. Download them one by one or as a single .zip."],
    ],
    body: [
      { h: "Why long Twitch VODs are hard to clip", p: [
        "Marathon streams can run 8 to 24 hours. The best moments are scattered: a chase in hour two, a rage moment in hour nine, a perfect heist near the end. Finding them by hand means scrubbing, rewinding and guessing.",
        `${BRAND} reads the audio of the whole VOD (sudden reactions, loud chaos, non-stop action) and turns every lively stretch into a 15–45 second moment you can judge in seconds.` ] },
      { h: "Sub-only and live streams", p: [
        "Subscriber-only VODs can't be downloaded, so they can't be clipped. If a stream is still live, wait for the VOD to appear once it ends." ] },
    ],
    faq: [
      ["Does it work with any Twitch VOD?", "Any public past broadcast or highlight works, plus Twitch clips. Subscriber-only VODs can't be accessed."],
      ["How long does a 12-hour VOD take?", "Usually a few minutes to scan. Twitch is a little slower than YouTube because its audio-only stream is larger."],
      ["Can I clip someone else's stream?", "Only if you have permission, for example through the creator's clipping program. Always follow their rules."],
      ["What resolution are the clips?", "Kept clips render from the 1080p stream: 1080×1920 for vertical layouts, or up to 1920×1080 for 16:9."],
    ],
    related: ["hub", "vertical", "campaigns"],
    cta: ["Clip your next Twitch VOD", "Paste the link and start reviewing in minutes."],
  },
  {
    slug: "youtube-stream-clipper",
    title: "YouTube stream clipper",
    metaTitle: "YouTube Stream Clipper: Turn Live Replays Into Shorts",
    description: `Turn YouTube live replays and long videos into Shorts. ${BRAND} scans the full video, finds the action, and exports captioned 9:16 clips.`,
    eyebrow: "YouTube stream clipper",
    h1: "Turn hours of YouTube live replays into ready-to-post Shorts",
    lead: "Paste any YouTube video or live replay. We scan the whole thing, use YouTube's own \"most replayed\" data when it's available, and line up the moments people actually rewatch.",
    benefits: [
      ["Built for long replays", "24-hour live replays are fine. The audio is scanned in parallel, so you're reviewing in minutes, not hours."],
      ["Uses \"most replayed\" data", "When a video has YouTube's replay heatmap, those peaks count toward which moments rank first."],
      ["Shorts-ready output", "Vertical 1080×1920 clips with optional burned-in captions, sized for Shorts, TikTok and Reels."],
    ],
    steps: [
      ["Copy the video link", "Any youtube.com/watch or youtube.com/live link works, including finished live streams."],
      ["Choose your layout", "Webcam on top + gameplay, blurred fill, center crop, or the original 16:9."],
      ["Review the moments", "Moments play instantly. Keep the good ones, skip the rest, trim if needed."],
      ["Export", "Download each clip or all of them as a .zip, then upload to Shorts."],
    ],
    body: [
      { h: "Long-form in, short-form out", p: [
        "A single long replay can feed a Shorts channel for a week. The hard part is finding the moments. Instead of skimming the timeline, you get a ranked list of every stretch with real action, each one 15 to 45 seconds with a little build-up so the payoff lands.",
        "Compilations, edited videos and podcasts work too: anything with audio energy." ] },
      { h: "End screens and intermissions", p: [
        "Edited uploads often finish on an end screen, and streams have \"be right back\" breaks. Static screens and full-screen camera segments are flagged automatically, so they don't clutter your review." ] },
    ],
    faq: [
      ["Can I clip a stream while it's live?", "Not yet. Wait until the stream ends and YouTube publishes the replay, then paste the link."],
      ["Do I need the video to be mine?", "Only clip videos you own or have permission to use, such as a creator's official clipping campaign."],
      ["How many moments will I get?", "About 13 per hour of video, more for short, dense videos. A 24-hour replay gives around 300."],
      ["Are captions automatic?", "Yes, on the Creator and Pro plans. Speech is transcribed and burned in with word-by-word highlighting."],
    ],
    related: ["hub", "captions", "twitch"],
    cta: ["Turn your replay into Shorts", "Scan a whole YouTube stream in minutes."],
  },
  {
    slug: "vertical-video-converter",
    title: "Stream to 9:16 converter",
    metaTitle: "Stream to Vertical Video: 9:16 Webcam + Gameplay Layout",
    description: `Convert gaming streams to vertical 9:16 video with the webcam on top and gameplay below. ${BRAND} finds the webcam automatically.`,
    eyebrow: "9:16 converter",
    h1: "Convert gaming streams to 9:16 with the webcam on top",
    lead: "The layout that works best for stream clips on TikTok, Shorts and Reels: the streamer's face up top, the gameplay underneath. We find the webcam for you.",
    benefits: [
      ["Webcam auto-detect", "The webcam overlay is found by spotting the same face in the same place across hours of the stream, then snapped to the overlay's border."],
      ["Four layouts", "Webcam + gameplay, full frame over a blurred fill, center crop, or the original 16:9."],
      ["Draw it yourself", "If a stream has an unusual layout, drag a box around the webcam once and every clip follows."],
    ],
    steps: [
      ["Pick a layout", "Choose \"9:16 webcam + gameplay\" when you create the project."],
      ["Let it find the webcam", "Auto-detect runs on moments spread across the whole stream."],
      ["Adjust if needed", "Open any kept clip and choose Webcam to draw the box manually."],
      ["Re-make in one click", "Change the layout for any clip without counting another export."],
    ],
    body: [
      { h: "Which vertical layout should I use?", p: [
        "Webcam + gameplay works best when the streamer's reaction is the point: rage, laughter, disbelief. Blurred fill keeps the whole frame visible, which suits wide shots and scenery. Center crop gives the biggest gameplay when the action is in the middle of the screen.",
        "You can switch layouts per clip, so it's easy to post the same moment two ways and see what performs better." ] },
      { h: "Resolution and quality", p: [
        "Vertical clips are rendered at 1080×1920 from the 1080p source, at up to 30 fps. Horizontal clips keep the source frame rate up to 60 fps." ] },
    ],
    faq: [
      ["What if the stream has no webcam?", "Use blurred fill or center crop. Webcam + gameplay falls back to a corner crop if no webcam is found."],
      ["Can I move the webcam box?", "Yes. Open a kept clip, choose Webcam, and drag a new box. You can apply it to every clip in the project."],
      ["Does it work for non-GTA streams?", "Yes. Any game or IRL stream with a webcam overlay works."],
      ["Is there a watermark?", "Only on the Free plan, as a small badge. Creator and Pro exports have no watermark."],
    ],
    related: ["hub", "captions", "twitch"],
    cta: ["Make your first 9:16 clip", "Webcam on top, gameplay below, found automatically."],
  },
  {
    slug: "auto-captions-for-gaming-clips",
    title: "Auto captions for gaming clips",
    metaTitle: "Auto Captions for Gaming Clips: Word-by-Word Highlights",
    description: `Add bold, word-by-word captions to gaming clips automatically. ${BRAND} transcribes the streamer and burns captions into every 9:16 clip.`,
    eyebrow: "Auto captions",
    h1: "Bold, word-by-word captions on every gaming clip",
    lead: "Most short-form viewers scroll with the sound off. Captions keep them watching. We transcribe the streamer and burn in big, readable captions with the current word highlighted.",
    benefits: [
      ["Automatic", "Speech is transcribed when the clip is made. Nothing to type, nothing to sync."],
      ["Built for phones", "Three words at a time, heavy outline, placed clear of the TikTok and Shorts buttons."],
      ["Skips the noise", "Music, silence and sound effects are filtered out so you don't get junk captions."],
    ],
    steps: [
      ["Turn on captions", "Tick \"Burned-in captions\" when you create a project, or switch them on in the kept-clips tray."],
      ["Keep a moment", "When you keep a moment, the speech is transcribed as the clip is made."],
      ["Download", "Captions are burned into the video, so they show on every platform."],
    ],
    body: [
      { h: "Why captions matter for stream clips", p: [
        "Streamer reactions are half the appeal of a clip, but the words are often lost under game audio. Captions make the joke land even on mute, and highlighting the spoken word keeps the eye moving.",
        "Captions are generated per clip, so re-trimming a clip re-times the captions automatically." ] },
    ],
    faq: [
      ["Which plans include captions?", "Creator and Pro. The Free plan can export clips without captions."],
      ["What languages are supported?", "English today. More languages are on the roadmap."],
      ["Can I edit the caption text?", "Not yet. If a word is wrong, try re-making the clip with a slightly different trim."],
    ],
    related: ["vertical", "hub", "youtube"],
    cta: ["Add captions to your clips", "Available on the Creator and Pro plans."],
  },
];
