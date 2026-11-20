"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { fmtTime } from "@/lib/site";
import type { Me } from "@/lib/types";

type Info = { title: string; duration: number; uploader: string; platform: string; thumbnail?: string };
const LAYOUTS: [string, string, React.ReactNode][] = [
  ["vertical_facecam", "9:16 webcam + gameplay", <span key="a" className="pv"><i className="cam" /><i /></span>],
  ["vertical_blur", "9:16 blurred fill", <span key="b" className="pv"><i className="blur" /><i /><i className="blur" /></span>],
  ["vertical_crop", "9:16 center crop", <span key="c" className="pv"><i /></span>],
  ["horizontal", "16:9 original", <span key="d" className="pv h"><i /></span>],
];
const CORNERS: [string, string][] = [["auto", "Auto-detect"], ["top-left", "↖"], ["top-right", "↗"], ["bottom-left", "↙"], ["bottom-right", "↘"]];

export default function NewProject() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [url, setUrl] = useState("");
  const [info, setInfo] = useState<Info | null>(null);
  const [probing, setProbing] = useState(false);
  const [layout, setLayout] = useState("vertical_facecam");
  const [captions, setCaptions] = useState(false);
  const [corner, setCorner] = useState("auto");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [clipLen, setClipLen] = useState(45);
  const [error, setError] = useState<{ msg: string; upgrade?: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    document.title = "New project · Hypecut";
    api<Me>("/api/me").then(m => { setMe(m); setCaptions(m.limits.captions); }).catch(e => setError({ msg: e.message }));
  }, []);

  useEffect(() => {
    const u = url.trim(); const my = ++seq.current;
    setInfo(null);
    if (!/^https?:\/\//.test(u)) return;
    setProbing(true);
    const t = setTimeout(async () => {
      try { const i = await api<Info>("/api/probe", { url: u }); if (my === seq.current) { setInfo(i); setError(null); } }
      catch (caught) { const e = caught as ApiError; if (my === seq.current) setError({ msg: e.message }); }
      finally { if (my === seq.current) setProbing(false); }
    }, 500);
    return () => clearTimeout(t);
  }, [url]);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      const r = await api<{ id: string }>("/api/projects", { url: url.trim(), format: layout, captions, facecam_corner: corner,
        clip_len: clipLen, start: start.trim(), end: end.trim() });
      router.push(`/app/p/${r.id}`);
    } catch (caught) { const err = caught as ApiError;
      setError({ msg: err.message, upgrade: (err as ApiError).upgrade }); setBusy(false);
    }
  }

  const left = me ? Math.max(0, me.limits.hours - me.usage.hours) : 0;
  const hrs = info ? info.duration / 3600 : 0;
  const warn = !me || !info ? "" : hrs > me.limits.max_video_hours
    ? `Your plan scans up to ${me.limits.max_video_hours} hours per video. Set a range under Advanced options, or upgrade.`
    : hrs > left ? `This needs ${hrs.toFixed(1)} hours and you have ${left.toFixed(1)} left this month. Set a shorter range, or upgrade.` : "";
  const est = info ? Math.round(Math.max(Math.min((info.duration / 60) * 1.5, 15), (info.duration / 60) * 0.22)) : 0;

  return (
    <div className="container app-page" style={{ maxWidth: 860 }}>
      <div className="page-head"><div><h1>New project</h1><p>Paste a stream. We&apos;ll find every moment with action.</p></div></div>
      <form className="card" onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 22, padding: 26 }} autoComplete="off">
        <label className="field">YouTube or Twitch link
          <input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://www.twitch.tv/videos/…  or  https://youtube.com/watch?v=…"
            style={{ fontSize: 17, padding: "15px 16px" }} required autoFocus />
        </label>
        {(probing || info) && (
          <div className="card" style={{ display: "flex", gap: 14, alignItems: "center", padding: 12, background: "var(--panel2)" }}>
            {/* eslint-disable-next-line @next/next/no-img-element -- remote video thumbnail */}
            {info?.thumbnail ? <img src={info.thumbnail} alt="" style={{ width: 132, aspectRatio: "16/9", objectFit: "cover", borderRadius: 8 }} />
              : <div style={{ width: 132, aspectRatio: "16/9", borderRadius: 8, background: "#000", display: "grid", placeItems: "center" }}><div className="spin" /></div>}
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 700 }}>{info ? info.title : "Looking up video…"}</div>
              {info && <div className="muted" style={{ fontSize: 14 }}>{[info.platform, info.uploader, info.duration ? fmtTime(info.duration) : ""].filter(Boolean).join(" · ")}{info.duration ? ` · about ${est} moments` : ""}</div>}
              {warn && <div style={{ fontSize: 14, color: "var(--sun)", marginTop: 4 }}>{warn}</div>}
            </div>
          </div>
        )}

        <div>
          <div className="field" style={{ marginBottom: 10 }}>Clip layout</div>
          <div className="fmt-grid" role="radiogroup">
            {LAYOUTS.map(([v, label, pv]) => (
              <label key={v} className="fmt"><input type="radio" name="fmt" value={v} checked={layout === v} onChange={() => setLayout(v)} />{pv}{label}</label>
            ))}
          </div>
        </div>

        <div className="row" style={{ gap: 22 }}>
          <label className="check"><input type="checkbox" checked={captions} disabled={!me?.limits.captions} onChange={e => setCaptions(e.target.checked)} />
            Burned-in captions {me && !me.limits.captions && <Link className="lock" href="/pricing" style={{ textDecoration: "none" }}>🔒 Creator plan</Link>}</label>
          {layout === "vertical_facecam" && (
            <div className="row" style={{ gap: 8 }}><span className="muted" style={{ fontSize: 14 }}>Webcam</span>
              <div className="seg">{CORNERS.map(([v, l]) => <button type="button" key={v} className={corner === v ? "on" : ""} onClick={() => setCorner(v)}>{l}</button>)}</div>
            </div>
          )}
        </div>

        <details>
          <summary style={{ cursor: "pointer", color: "var(--muted)", fontWeight: 600 }}>Advanced options</summary>
          <div className="form-grid" style={{ marginTop: 14 }}>
            <label className="field">Scan from <input value={start} onChange={e => setStart(e.target.value)} placeholder="start (e.g. 2:00:00)" /></label>
            <label className="field">Scan to <input value={end} onChange={e => setEnd(e.target.value)} placeholder="end" /></label>
            <label className="field">Longest moment (seconds) <input type="number" min={15} max={60} value={clipLen} onChange={e => setClipLen(+e.target.value)} /></label>
          </div>
          <p className="muted" style={{ fontSize: 13, marginTop: 10 }}>Leave the range empty to scan the whole video. Use a range to save hours, or to fit a long stream into your plan&apos;s per-video limit.</p>
        </details>

        {me && (me.plan === "free"
          ? <div className="upgrade-note"><span>Free plan: <b>{left.toFixed(1)} of {me.limits.hours} hours</b> left this month, exports include a small watermark.</span><Link href="/pricing">See plans →</Link></div>
          : <p className="muted" style={{ fontSize: 14 }}>{left.toFixed(1)} hours of scanning left this month on {me.limits.name}.</p>)}

        {error && <div className="form-error" role="alert">{error.msg} {error.upgrade && <Link href="/pricing" style={{ color: "#fff", fontWeight: 700 }}>See plans →</Link>}</div>}
        <button className="btn btn-primary btn-lg" type="submit" disabled={busy}>{busy ? "Checking the video…" : "Find moments"}</button>
      </form>
    </div>
  );
}
