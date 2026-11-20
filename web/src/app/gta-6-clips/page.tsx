import type { Metadata } from "next";
import Link from "next/link";
import JsonLd from "@/components/JsonLd";
import Faq from "@/components/Faq";
import { Breadcrumbs, CtaBand, Related, faqJsonLd, howToJsonLd } from "@/components/Seo";
import { BRAND, SITE_URL } from "@/lib/site";

const TITLE = "GTA 6 Clip Maker: Turn GTA 6 Streams Into Viral Clips";
const DESC = `Make GTA 6 clips from any Twitch or YouTube stream in minutes. ${BRAND} scans the whole VOD, finds every chase, heist and reaction, and exports 9:16 clips with captions.`;

export const metadata: Metadata = {
  title: { absolute: `${TITLE} · ${BRAND}` },
  description: DESC,
  keywords: ["GTA 6 clips", "GTA 6 clip maker", "GTA VI clips", "clip GTA 6 streams", "GTA 6 TikTok clips",
    "GTA 6 Shorts", "GTA 6 highlights", "Twitch VOD clipper", "stream clipping tool", "GTA 6 clipping"],
  alternates: { canonical: "/gta-6-clips" },
  openGraph: { title: TITLE, description: DESC, url: "/gta-6-clips", type: "article" },
  twitter: { title: TITLE, description: DESC },
};

const STEPS: [string, string][] = [
  ["Find a GTA 6 stream or video", "Copy the link to a Twitch VOD, a YouTube live replay, or any YouTube video. It can be your own stream or a creator's stream you have permission to clip."],
  ["Paste it into a new project", "Choose a layout (webcam on top + gameplay is the most popular for TikTok and Shorts) and turn on captions if you want them. Optionally set a time range."],
  ["Let the whole stream get scanned", "The audio of the entire video is scanned, even 24-hour marathons, and every stretch with real action becomes a 15–45 second moment."],
  ["Review moments at keyboard speed", "Each moment previews instantly. Press K to keep, X to skip, and nudge the start or end by two seconds. Menus and \"be right back\" screens are flagged for you."],
  ["Download and post", "Kept clips render in HD with your layout, captions and the streamer's webcam framed automatically. Grab them one by one or as a .zip."],
];

const MOMENTS: [string, string][] = [
  ["🚓", "Police chases"], ["💰", "Heists & robberies"], ["💥", "Explosions & crashes"], ["🔫", "Shootouts"],
  ["😂", "Fails & glitches"], ["🤯", "Streamer reactions"], ["🏍️", "Vehicle stunts"], ["🌴", "Vice City sightseeing"],
  ["🎭", "Story & cutscene moments"], ["🤝", "Co-op chaos"], ["🐊", "Wildlife surprises"], ["🎉", "First-time reactions"],
];

const FORMATS: [string, string, string, string][] = [
  ["TikTok", "9:16 vertical", "15–45 seconds", "A strong hook in the first second, captions on, the webcam visible for reactions."],
  ["YouTube Shorts", "9:16 vertical", "20–50 seconds", "A clear payoff, a searchable title (\"GTA 6\" plus what happens), and loop-friendly endings."],
  ["Instagram Reels", "9:16 vertical", "15–40 seconds", "Big captions, fast pacing, and a cover frame that shows the action."],
  ["X (Twitter)", "16:9 or 9:16", "10–40 seconds", "Short and punchy, works well as reply bait during a big stream."],
];

const FAQ: [string, string][] = [
  ["What is the best way to make GTA 6 clips?", `Start from the full VOD rather than live clips. With ${BRAND} you paste the VOD link, every action-heavy moment is lined up for you, and you keep the best ones as vertical clips with captions. That's far faster than scrubbing through hours of video.`],
  ["Can I clip any GTA 6 streamer?", "Only clip streams you own or have permission to use. Many big streamers run official clipping programs that pay clippers per view; join those and follow their rules."],
  ["How long does it take to scan a GTA 6 stream?", "A few minutes for most streams. A 12-hour YouTube replay is usually ready to review in under five minutes; Twitch takes a little longer."],
  ["How many clips can I get from one stream?", "About 13 moments per hour of stream. A 24-hour marathon gives roughly 300 moments to review, and you choose which become clips."],
  ["What's the best length for GTA 6 clips?", "Most viral stream clips land between 15 and 45 seconds: enough build-up for context, and a fast payoff. Moments are sized automatically within that range."],
  ["Does it work for GTA 6 Online and roleplay streams?", "Yes. Anything with a stream and audio works: story mode, online sessions, roleplay servers and co-op."],
  ["Will my clips have a watermark?", "Only on the Free plan, as a small badge. Creator and Pro clips have no watermark."],
  ["Can I add captions to GTA 6 clips?", "Yes, on the Creator and Pro plans. Speech is transcribed automatically and burned in with word-by-word highlighting."],
  ["Is this affiliated with Rockstar Games?", `No. ${BRAND} is an independent tool for clipping streams. It's not affiliated with or endorsed by Rockstar Games or Take-Two Interactive.`],
  ["Do I need to download the VOD first?", "No. Paste the link and the video is fetched for you. Only the moments you keep are downloaded in HD."],
];

const GLOSSARY: [string, string][] = [
  ["VOD", "Video on demand: the saved recording of a livestream, viewable after it ends."],
  ["Clipping", "Cutting short highlights out of long streams to post on short-form platforms."],
  ["Clipping campaign", "A paid program where a streamer or brand pays clippers based on the views their clips get."],
  ["CPM", "Cost per mille: a payout per 1,000 views, e.g. $1 CPM pays $1 for every 1,000 views."],
  ["9:16", "The tall vertical format used by TikTok, Shorts and Reels (1080×1920 pixels)."],
  ["Facecam / webcam overlay", "The box in a stream showing the streamer's camera, usually in a corner over the gameplay."],
  ["Hook", "The first one or two seconds of a clip that make a viewer stop scrolling."],
  ["Burned-in captions", "Subtitles drawn into the video itself, so they show on every platform without settings."],
];

export default function Gta6Clips() {
  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org", "@type": "WebPage", name: TITLE, description: DESC, url: `${SITE_URL}/gta-6-clips`,
        about: { "@type": "Thing", name: "Grand Theft Auto VI stream clips" },
        mainEntity: { "@type": "SoftwareApplication", name: BRAND, applicationCategory: "MultimediaApplication", operatingSystem: "Web",
          offers: { "@type": "Offer", price: "0", priceCurrency: "USD" } },
      }} />
      <JsonLd data={howToJsonLd("How to make GTA 6 clips from a stream", "Turn a long GTA 6 Twitch or YouTube stream into short vertical clips.", STEPS)} />
      <JsonLd data={faqJsonLd(FAQ)} />

      <section className="seo-hero">
        <div className="container">
          <Breadcrumbs items={[["GTA 6 clips", "/gta-6-clips"]]} />
          <span className="pill"><span className="dot" /> GTA 6 clip maker</span>
          <h1>Turn every GTA 6 stream into <span className="grad-text">viral clips</span>, in minutes</h1>
          <p className="lead">Paste a Twitch or YouTube link. {BRAND} scans the entire stream (chases, heists, crashes, reactions) and lines up every moment worth posting. Keep the best, and download 9:16 clips with the webcam framed and captions burned in.</p>
          <div className="hero-ctas">
            <Link className="btn btn-primary btn-lg" href="/signup">Make GTA 6 clips free</Link>
            <a className="btn btn-outline btn-lg" href="#how">How it works</a>
          </div>
          <div className="trust"><span>Whole streams, even 24 hours</span><span>Webcam found automatically</span><span>Word-by-word captions</span><span>Free plan, no card</span></div>
          <nav className="toc" aria-label="On this page">
            {[["#why", "Why GTA 6 clips"], ["#how", "How to clip"], ["#moments", "What we find"], ["#layouts", "Layouts"], ["#formats", "Platform formats"],
              ["#compare", "Manual vs " + BRAND], ["#who", "Who it's for"], ["#tips", "Going viral"], ["#campaigns", "Campaigns"], ["#glossary", "Glossary"], ["#faq", "FAQ"]]
              .map(([h, l]) => <a key={h} href={h}>{l}</a>)}
          </nav>
        </div>
      </section>

      <section className="block" id="why"><div className="container article">
        <h2>Why GTA 6 clips are everywhere right now</h2>
        <p>GTA 6 is the biggest game launch in years, and its streams are long: marathon sessions of 10, 12, even 24 hours are common. Inside every one are dozens of moments people want to rewatch: a getaway that goes perfectly wrong, a chase that ends in the ocean, a streamer losing it at a cutscene.</p>
        <p>Short-form platforms reward exactly these moments. But nobody has time to watch a full marathon to find them. That gap, hours of footage and seconds of gold, is what a clip maker closes.</p>
        <div className="grid-3" style={{ marginTop: 22 }}>
          <div className="card mini"><h3>~300 moments</h3><p>found in a single 24-hour stream, ready to review.</p></div>
          <div className="card mini"><h3>&lt;1 second</h3><p>to load each preview, so reviewing feels instant.</p></div>
          <div className="card mini"><h3>15–45 seconds</h3><p>per moment, sized to the action, with a little build-up.</p></div>
        </div>
      </div></section>

      <section className="block" id="how"><div className="container article">
        <h2>How to make GTA 6 clips from a stream</h2>
        <p>The whole process takes minutes, even for marathon streams.</p>
        <ol className="numbered">
          {STEPS.map(([h, t]) => <li key={h}><b>{h}</b>{t}</li>)}
        </ol>
        <div className="callout">Tip: scan the whole stream rather than just the first hour. The funniest moments often happen late, when the streamer is tired and the chat is loud.</div>
      </div></section>

      <section className="block" id="moments"><div className="container">
        <div className="article"><h2>What kinds of GTA 6 moments get found</h2>
          <p>Moments are scored from the stream&apos;s audio: sudden spikes (a scream, a crash), sustained activity (a chase or shootout that keeps going), and loud stretches above the stream&apos;s normal level. That catches:</p></div>
        <div className="chips" style={{ maxWidth: 860, margin: "18px auto 0" }}>
          {MOMENTS.map(([i, l]) => <span key={l} className="chip-lg"><i aria-hidden="true">{i}</i>{l}</span>)}
        </div>
      </div></section>

      <section className="block" id="layouts"><div className="container">
        <div className="article"><h2>Layouts for GTA 6 clips</h2>
          <p>Pick a layout per project, and change it per clip any time.</p></div>
        <div className="grid-4 layout-cards" style={{ marginTop: 18 }}>
          <div className="card mini" style={{ textAlign: "center" }}><div className="lp"><i className="cam" /><i /></div><h3>Webcam + gameplay</h3><p>Streamer on top, game below. Best for reactions.</p></div>
          <div className="card mini" style={{ textAlign: "center" }}><div className="lp"><i className="blur" /><i /><i className="blur" /></div><h3>Blurred fill</h3><p>The full frame on a soft background. Best for wide shots.</p></div>
          <div className="card mini" style={{ textAlign: "center" }}><div className="lp"><i /></div><h3>Center crop</h3><p>The biggest gameplay. Best when action is centered.</p></div>
          <div className="card mini" style={{ textAlign: "center" }}><div className="lp h"><i /></div><h3>Original 16:9</h3><p>For YouTube, X and Discord.</p></div>
        </div>
      </div></section>

      <section className="block" id="formats"><div className="container">
        <div className="article"><h2>GTA 6 clip formats for each platform</h2>
          <p>All vertical exports are 1080×1920. These are the lengths and habits that tend to work for stream clips; platform limits change, so check each app&apos;s current rules.</p></div>
        <div className="table-wrap" style={{ maxWidth: 980, margin: "18px auto 0" }}>
          <table className="compare">
            <thead><tr><th>Platform</th><th>Format</th><th>Sweet spot</th><th style={{ textAlign: "left" }}>What works</th></tr></thead>
            <tbody>{FORMATS.map(([p, f, l, w]) => <tr key={p}><td><b>{p}</b></td><td>{f}</td><td>{l}</td><td style={{ textAlign: "left" }}>{w}</td></tr>)}</tbody>
          </table>
        </div>
      </div></section>

      <section className="block" id="compare"><div className="container">
        <div className="article"><h2>Clipping GTA 6 by hand vs with {BRAND}</h2></div>
        <div className="table-wrap" style={{ maxWidth: 980, margin: "18px auto 0" }}>
          <table className="compare">
            <thead><tr><th>Task</th><th>By hand</th><th>{BRAND}</th></tr></thead>
            <tbody>
              <tr><td>Finding moments in a 12-hour stream</td><td>Hours of scrubbing</td><td>Minutes; every moment lined up</td></tr>
              <tr><td>Downloading the VOD</td><td>Whole file, many GB</td><td>Nothing until you keep a clip</td></tr>
              <tr><td>Reframing to 9:16</td><td>Manual crop in an editor</td><td>Automatic, webcam detected</td></tr>
              <tr><td>Captions</td><td>Type or sync by hand</td><td>Automatic, word-by-word</td></tr>
              <tr><td>Skipping menus and breaks</td><td>Watch to find out</td><td>Flagged automatically</td></tr>
              <tr><td>Exporting 20 clips</td><td>One render at a time</td><td>Keep, then download all as .zip</td></tr>
            </tbody>
          </table>
        </div>
      </div></section>

      <section className="block" id="who"><div className="container">
        <div className="article"><h2>Who uses a GTA 6 clip maker</h2></div>
        <div className="grid-2" style={{ maxWidth: 980, margin: "18px auto 0" }}>
          <div className="card mini"><h3>🎮 Streamers</h3><p>Turn last night&apos;s marathon into a week of Shorts and TikToks without hiring an editor.</p></div>
          <div className="card mini"><h3>✂️ Clippers</h3><p>Post more clips, faster, while a moment is still trending. Volume is how clippers win.</p></div>
          <div className="card mini"><h3>💸 Campaign clippers</h3><p>Clip streamers who pay per view, and cover their whole stream instead of the first hour.</p></div>
          <div className="card mini"><h3>🏢 Agencies & editors</h3><p>Review hundreds of moments per stream and hand off only the best to your team.</p></div>
        </div>
      </div></section>

      <section className="block" id="tips"><div className="container article">
        <h2>How to make GTA 6 clips that go viral</h2>
        <h3>1. Win the first second</h3>
        <p>Start as close to the action as possible. Use the −2s nudge to cut slow build-up; keep just enough that the payoff makes sense.</p>
        <h3>2. Let the reaction carry it</h3>
        <p>Viewers share the streamer&apos;s reaction as much as the gameplay. The webcam-on-top layout keeps both on screen.</p>
        <h3>3. Caption everything</h3>
        <p>Many people watch without sound. Big captions keep them watching and make the joke land.</p>
        <h3>4. Post fast and post often</h3>
        <p>Big streams produce trending moments within hours. The clippers who post first, and post many variations, collect most of the views.</p>
        <h3>5. Write titles people search for</h3>
        <p>Say what happens, plus &quot;GTA 6&quot;. Some patterns that work:</p>
        <div className="title-ideas">
          <div>&quot;He did NOT expect that in GTA 6 😭&quot;</div>
          <div>&quot;The worst getaway in GTA 6 history&quot;</div>
          <div>&quot;GTA 6 physics are actually insane&quot;</div>
          <div>&quot;This GTA 6 chase ended in the ocean 🌊&quot;</div>
        </div>
        <h3>6. Hashtags that help</h3>
        <p>Keep them relevant: #GTA6, #GTAVI, #GTA6Clips, #Gaming, plus the streamer&apos;s tag when a campaign requires it.</p>
      </div></section>

      <section className="block" id="campaigns"><div className="container article">
        <h2>GTA 6 clipping campaigns</h2>
        <p>Many streamers and brands pay clippers to post highlights, usually per 1,000 views (CPM) or by splitting a prize pool by views. GTA 6 streams have some of the largest campaigns right now.</p>
        <p>Each campaign has rules (which streams to use, which platforms, required hashtags or credit), so read them before posting. Our full guide covers how payouts work and how to pick campaigns worth your time.</p>
        <p><Link href="/guides/gta-6-clipping-campaigns">Read the GTA 6 clipping campaigns guide →</Link></p>
      </div></section>

      <section className="block" id="glossary"><div className="container article">
        <h2>GTA 6 clipping glossary</h2>
        <dl className="glossary">{GLOSSARY.map(([t, d]) => <div key={t} style={{ display: "contents" }}><dt>{t}</dt><dd>{d}</dd></div>)}</dl>
      </div></section>

      <section className="block" id="faq"><div className="container">
        <div className="article"><h2>GTA 6 clips FAQ</h2></div>
        <div style={{ marginTop: 18 }}><Faq items={FAQ} openFirst /></div>
        <p className="disclaimer article">{BRAND} is an independent tool and is not affiliated with, endorsed by, or sponsored by Rockstar Games, Take-Two Interactive, Twitch or YouTube. &quot;GTA&quot;, &quot;Grand Theft Auto&quot; and related marks belong to their respective owners and are used here only to describe compatible content.</p>
      </div></section>

      <Related keys={["twitch", "youtube", "vertical", "captions", "campaigns", "pricing"]} title="More tools and guides" />
      <CtaBand title="Your next viral GTA 6 clip is already in the VOD." text="Paste a stream and start reviewing moments in minutes." cta="Make GTA 6 clips free" />
    </>
  );
}
