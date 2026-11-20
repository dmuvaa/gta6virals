import Link from "next/link";
import JsonLd from "@/components/JsonLd";
import Faq from "@/components/Faq";
import PricingCards from "@/components/PricingCards";
import { BRAND, FAQ, PLANS, SITE_URL } from "@/lib/site";

const WAVE = [30, 45, 25, 60, 80, 40, 35, 90, 100, 70, 45, 30, 55, 65, 40, 25, 35, 50, 30, 20, 45, 60, 35, 25];

function Icon({ d }: { d: string }) {
  return <svg viewBox="0 0 24 24"><path fill="currentColor" d={d} /></svg>;
}

const FEATURES = [
  { tone: "", title: "Whole streams, in minutes", d: "M13 2 4 14h7l-1 8 9-12h-7z",
    text: "We scan the full audio over many parallel connections and only download the moments you want in HD. Even 24-hour marathons." },
  { tone: "sun", title: "Finds the action, not just noise", d: "M3 13h2v-2H3zm4 4h2V7H7zm4 3h2V4h-2zm4-6h2v-4h-2zm4 2h2V8h-2z",
    text: "Reactions, screams, chases and shootouts all score. Every moment grows to fit the action, from 15 to 45 seconds with a short build-up." },
  { tone: "good", title: "Review at keyboard speed", d: "M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z",
    text: "Previews load instantly. Press K to keep, X to discard, nudge the start and end, and move on. Hundreds of moments in one sitting." },
  { tone: "violet", title: "Webcam found automatically", d: "M17 10.5V7a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-3.5l4 4v-11z",
    text: "The 9:16 layout puts the streamer's face cam on top and gameplay below. We find the webcam box for you, or you can draw it." },
  { tone: "sea", title: "Captions that pop", d: "M19 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2m-8 7H9.5v-.5h-2v3h2V13H11v1a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1zm7 0h-1.5v-.5h-2v3h2V13H18v1a1 1 0 0 1-1 1h-3a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1z",
    text: "Bold, word-by-word captions with the spoken word highlighted, transcribed automatically and burned into the clip." },
  { tone: "", title: "Skips the dead air", d: "M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2m1 15h-2v-6h2zm0-8h-2V7h2z",
    text: "Menus, loading screens, \"be right back\" and just-chatting segments get flagged automatically, so you spend your time on gameplay." },
];

export default function Home() {
  return (
    <>
      <JsonLd data={{
        "@context": "https://schema.org",
        "@graph": [
          { "@type": "Organization", name: BRAND, url: SITE_URL, logo: `${SITE_URL}/apple-icon.png` },
          { "@type": "WebSite", name: BRAND, url: SITE_URL },
          { "@type": "SoftwareApplication", name: BRAND, applicationCategory: "MultimediaApplication", operatingSystem: "Web",
            url: SITE_URL, offers: PLANS.map(p => ({ "@type": "Offer", name: p.name, price: String(p.price), priceCurrency: "USD" })) },
          { "@type": "FAQPage", mainEntity: FAQ.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })) },
        ],
      }} />

      <section className="hero">
        <div className="container hero-inner">
          <div>
            <span className="pill"><span className="dot" /> Built for <b>GTA VI</b> stream clippers</span>
            <h1>Every hype moment.<br /><span className="grad-text">One 12-hour stream.</span><br />A few minutes.</h1>
            <p className="lead">Paste a YouTube or Twitch link. {BRAND} scans the whole stream and lines up every moment with action. Play through them, keep the bangers, and export ready-to-post 9:16 clips with captions.</p>
            <div className="hero-ctas">
              <Link className="btn btn-primary btn-lg" href="/signup">Start clipping free</Link>
              <Link className="btn btn-outline btn-lg" href="#how">See how it works</Link>
            </div>
            <p className="hero-note">Free plan · No credit card · 3 hours of video every month</p>
            <div className="stats">
              <div className="stat"><b>~300</b><span>moments from a 24-hour stream</span></div>
              <div className="stat"><b>&lt;1s</b><span>to load each preview</span></div>
              <div className="stat"><b>9:16</b><span>webcam + gameplay, auto-framed</span></div>
            </div>
          </div>
          <div style={{ position: "relative" }}>
            <div className="mock" role="img" aria-label="The review workspace: a stream moment playing with captions, a list of moments, and Keep and Discard buttons">
              <div className="mock-bar"><i /><i /><i /></div>
              <div className="mock-grid">
                <div>
                  <div className="mock-player">
                    <div className="sun" /><div className="road" />
                    <div className="palm" style={{ left: "12%" }} /><div className="palm" style={{ left: "84%", height: "30%" }} />
                    <div className="cam" />
                    <span className="tag">#12 · 0:34</span>
                    <div className="cap">NO WAY HE <em>JUMPED</em></div>
                  </div>
                  <div className="mock-wave">{WAVE.map((h, i) => <i key={i} style={{ height: `${h}%` }} className={i >= 7 && i <= 10 ? "on" : ""} />)}</div>
                  <div className="mock-actions"><div className="d">✕ Discard</div><div className="k">✓ Keep</div></div>
                </div>
                <div className="mock-list">
                  {[["2:08:24", "32s · Sudden reaction", "kept"], ["3:41:48", "34s · Non-stop action", "cur"], ["4:51:52", "28s · Loud moment", ""],
                    ["6:52:11", "41s · Non-stop action", "kept"], ["10:58:44", "19s · Sudden reaction", ""], ["15:54:32", "22s · Loud moment", ""]].map(([t, s, c]) => (
                    <div key={t} className={`mock-item ${c}`}><b>{t}</b><span>{s}</span></div>
                  ))}
                </div>
              </div>
            </div>
            <div className="float-card float-1"><span className="ic" style={{ background: "#3ddc841f" }}>✓</span><div><b>314 moments</b><div className="muted">found in a 24h stream</div></div></div>
            <div className="float-card float-2"><span className="ic" style={{ background: "#ff4f8b1f" }}>CC</span><div><b>Captions on</b><div className="muted">word-by-word</div></div></div>
          </div>
        </div>
      </section>

      <div className="strip"><div className="container strip-inner">
        <span>▶ YouTube streams &amp; videos</span><span>● Twitch VODs &amp; clips</span><span>⬇ Exports for TikTok · Shorts · Reels · X</span>
      </div></div>

      <section className="section" id="features">
        <div className="container">
          <div className="section-head">
            <span className="eyebrow">Features</span>
            <h2>Stop scrubbing. Start posting.</h2>
            <p>Long streams are full of great moments. Finding them by hand takes hours. {BRAND} does the finding, and you do the picking.</p>
          </div>
          <div className="features">
            {FEATURES.map(f => (
              <div key={f.title} className="card feature">
                <div className={`icon ${f.tone}`}><Icon d={f.d} /></div>
                <h3>{f.title}</h3><p>{f.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section" id="how" style={{ background: "var(--bg2)" }}>
        <div className="container">
          <div className="section-head"><span className="eyebrow">How it works</span><h2>From VOD to posted in three steps</h2></div>
          <div className="steps">
            <div className="card step"><h3>Paste a link</h3><p>Any YouTube video or stream replay, or any Twitch VOD or clip. Pick your layout, and turn on captions if you want them.</p></div>
            <div className="card step"><h3>Review the moments</h3><p>We line up every moment with action, best first. Play, keep or discard, and trim. Flagged non-gameplay is hidden for you.</p></div>
            <div className="card step"><h3>Download &amp; post</h3><p>Kept clips are made in HD in seconds. Download them one by one or all at once, then post to TikTok, Shorts, Reels and X.</p></div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container split">
          <div>
            <span className="eyebrow">For clipping campaigns</span>
            <h2>Post more clips. Get more views. Earn more.</h2>
            <p>Streamers and brands pay clippers per view. The clippers who win post a lot, and post fast. {BRAND} turns one marathon stream into a week of content in a single sitting.</p>
            <ul className="ticks">
              <li>Clip the whole stream, not just the first hour</li>
              <li>Post while the moment is still trending</li>
              <li>Fresh trims and captions on every clip, not the same cut everyone posts</li>
              <li>One download for all your kept clips</li>
            </ul>
            <p className="muted" style={{ fontSize: 14, marginTop: 20 }}>Always follow each campaign&apos;s rules and only clip content you have permission to use.</p>
          </div>
          <div className="phone-row" aria-hidden="true">
            <div className="phone"><div className="top" /><div className="bottom" /><div className="cap">HE DID <em>WHAT</em></div></div>
            <div className="phone alt"><div className="top" /><div className="bottom" /><div className="cap" style={{ top: "72%" }}>LET&apos;S <em>GO</em></div></div>
          </div>
        </div>
      </section>

      <section className="section" id="pricing" style={{ background: "var(--bg2)" }}>
        <div className="container">
          <div className="section-head"><span className="eyebrow">Pricing</span><h2>Start free. Upgrade when you&apos;re posting daily.</h2><p>Simple monthly plans. Cancel anytime.</p></div>
          <PricingCards />
        </div>
      </section>

      <section className="section" id="faq">
        <div className="container">
          <div className="section-head"><span className="eyebrow">FAQ</span><h2>Questions, answered</h2></div>
          <Faq items={FAQ} />
        </div>
      </section>

      <section className="section-tight">
        <div className="container">
          <div className="cta-band">
            <h2>Your next viral clip is already in the VOD.</h2>
            <p>Find it in minutes, not hours.</p>
            <Link className="btn btn-primary btn-lg" href="/signup">Start clipping free</Link>
          </div>
        </div>
      </section>
    </>
  );
}
