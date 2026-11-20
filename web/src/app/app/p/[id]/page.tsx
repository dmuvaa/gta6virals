"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, downloadWithAuth } from "@/lib/api";
import { fmtTime } from "@/lib/site";
import type { Moment, Project } from "@/lib/types";

const FMT: Record<string, string> = { horizontal: "16:9", vertical_blur: "9:16 blur", vertical_crop: "9:16 crop", vertical_facecam: "9:16 webcam" };
const REASON_CLS: Record<string, string> = { "Loud moment": "", "Sudden reaction": "r", "Non-stop action": "a", "High action": "a", "Most replayed": "m" };
const FLAG_TXT: Record<string, string> = { static: "Static screen?", camera: "Not gameplay?" };
const BUSY = ["queued", "downloading", "captioning", "rendering"];
type Preview = { url: string; start: number; end: number };
type Tab = "new" | "kept" | "discarded";
type Rect = { x: number; y: number; w: number; h: number };

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [job, setJob] = useState<Project | null>(null);
  const [loadErr, setLoadErr] = useState("");
  const [tab, setTab] = useState<Tab>("new");
  const [sort, setSort] = useState<"best" | "time">("best");
  const [hideFlag, setHideFlag] = useState(true);
  const [cur, setCur] = useState<string | null>(null);
  const [pv, setPv] = useState<Preview | null>(null);
  const [pvState, setPvState] = useState<"idle" | "loading" | string>("idle");
  const [progress, setProgress] = useState(0);
  const [autoAdvance, setAutoAdvance] = useState(true);
  const [toast, setToast] = useState<{ msg: string; upgrade?: boolean } | null>(null);
  const [cam, setCam] = useState<{ moment: Moment; url?: string; rect: Rect | null; err?: string; all: boolean; saving?: boolean } | null>(null);
  const vid = useRef<HTMLVideoElement>(null);
  const cache = useRef<Record<string, Promise<Preview>>>({});
  const listRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<HTMLCanvasElement>(null);
  const settingsInit = useRef(false);
  const [keptFmt, setKeptFmt] = useState("vertical_facecam");
  const [keptCaps, setKeptCaps] = useState(false);
  const [captionsAllowed, setCaptionsAllowed] = useState(false);

  const say = useCallback((msg: string, upgrade?: boolean) => {
    setToast({ msg, upgrade }); setTimeout(() => setToast(null), upgrade ? 9000 : 5000);
  }, []);

  // ---------------------------------------------------------------- polling
  const load = useCallback(async () => {
    try {
      const j = await api<Project>(`/api/projects/${id}`);
      setJob(j); setLoadErr("");
      if (!settingsInit.current) { setKeptFmt(j.settings.format || "vertical_facecam"); setKeptCaps(!!j.settings.captions); settingsInit.current = true; }
      return j;
    } catch (caught) { const e = caught as ApiError; if ((e as ApiError).status === 404) setLoadErr("This project doesn't exist or was deleted."); return null; }
  }, [id]);
  useEffect(() => {
    let t: ReturnType<typeof setTimeout>; let alive = true;
    const tick = async () => {
      const j = await load();
      if (!alive) return;
      const working = j && !["review", "done", "error", "cancelled"].includes(j.stage);
      const rendering = j?.moments.some(m => m.state === "kept" && BUSY.includes(m.status));
      if (j && j.stage !== "error" && j.stage !== "cancelled") t = setTimeout(tick, working ? 1000 : rendering ? 1500 : 4000);
    };
    tick();
    api<{ limits: { captions: boolean } }>("/api/me").then(m => setCaptionsAllowed(m.limits.captions)).catch(() => {});
    return () => { alive = false; clearTimeout(t); };
  }, [load]);
  useEffect(() => { if (job?.title) document.title = `${job.title} · Hypecut`; }, [job?.title]);

  const moments = useMemo(() => job?.moments || [], [job?.moments]);
  const byId = useCallback((mid: string | null) => moments.find(m => m.id === mid), [moments]);
  const visible = useMemo(() => {
    const v = moments.filter(m => m.state === tab && !(hideFlag && tab === "new" && m.flag));
    return v.sort(sort === "time" ? (a, b) => a.start - b.start : (a, b) => a.rank - b.rank);
  }, [moments, tab, sort, hideFlag]);
  const counts = useMemo(() => ({
    new: moments.filter(m => m.state === "new").length, kept: moments.filter(m => m.state === "kept").length,
    discarded: moments.filter(m => m.state === "discarded").length, flagged: moments.filter(m => m.state === "new" && m.flag).length,
  }), [moments]);
  const reviewing = job?.stage === "review";

  // ---------------------------------------------------------------- previews
  const preview = useCallback((m: Moment) => {
    const key = `${m.id}|${m.start}|${m.end}`;
    if (!cache.current[key]) cache.current[key] = api<Preview>(`/api/projects/${id}/moments/${m.id}/preview`, {})
      .catch(e => { delete cache.current[key]; throw e; });
    return cache.current[key];
  }, [id]);

  const play = useCallback(async (mid: string, seekEnd = false) => {
    const m = byId(mid); if (!m) return;
    setPvState("loading"); vid.current?.pause();
    try {
      const p = await preview(m);
      setCur(c => { if (c === mid) { setPv(p); setPvState("idle"); const v = vid.current;
        if (v) { if (v.dataset.src !== p.url) { v.src = p.url; v.dataset.src = p.url; }
          v.currentTime = seekEnd ? Math.max(p.start, p.end - 3) : p.start; v.play().catch(() => {}); } }
        return c; });
    } catch (caught) { const e = caught as ApiError; setCur(c => { if (c === mid) setPvState(e.message); return c; }); }
  }, [byId, preview]);

  const select = useCallback((mid: string) => {
    setCur(mid);
    setTimeout(() => play(mid), 0);
    const i = visible.findIndex(m => m.id === mid);
    visible.slice(i + 1, i + 4).forEach(m => preview(m).catch(() => {}));  // warm up the next few
    listRef.current?.querySelector(`[data-id="${mid}"]`)?.scrollIntoView({ block: "nearest" });
  }, [play, preview, visible]);

  useEffect(() => { if (reviewing && !cur && visible.length) select(visible[0].id); }, [reviewing, cur, visible, select]);

  // ---------------------------------------------------------------- actions
  const step = useCallback((d: number) => {
    if (!visible.length) return;
    let i = visible.findIndex(m => m.id === cur);
    i = i < 0 ? 0 : Math.min(visible.length - 1, Math.max(0, i + d));
    select(visible[i].id);
  }, [visible, cur, select]);

  const patchMoment = (mid: string, vals: Partial<Moment>) =>
    setJob(j => j && { ...j, moments: j.moments.map(m => (m.id === mid ? { ...m, ...vals } : m)) });

  const decide = useCallback(async (state: Tab) => {
    const m = byId(cur); if (!m) return;
    const i = visible.findIndex(x => x.id === m.id);
    const nextId = (visible[i + 1] || visible[i - 1])?.id;
    const target: Tab = m.state === state ? "new" : state;  // pressing again undoes
    const prev = { state: m.state, status: m.status };
    patchMoment(m.id, { state: target, ...(target === "kept" ? { status: "queued" } : {}) });
    try { patchMoment(m.id, await api<Moment>(`/api/projects/${id}/moments/${m.id}`, { state: target })); }
    catch (caught) { const e = caught as ApiError; patchMoment(m.id, prev as Partial<Moment>); return say(e.message, e.upgrade); }
    if (tab === "new" && target !== "new" && nextId) select(nextId);
  }, [byId, cur, visible, id, tab, select, say]);

  const nudge = useCallback(async (which: "s" | "e", d: number) => {
    const m = byId(cur); if (!m || !job) return;
    const ws = job.window[0];
    try {
      const upd = await api<Moment>(`/api/projects/${id}/moments/${m.id}`, {
        start: m.start + ws + (which === "s" ? d : 0), end: m.end + ws + (which === "e" ? d : 0) });
      patchMoment(m.id, upd);
      setTimeout(() => play(m.id, which === "e"), 0);
    } catch (caught) { const e = caught as ApiError; say(e.message); }
  }, [byId, cur, job, id, play, say]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!reviewing || cam || e.metaKey || e.ctrlKey || e.altKey) return;
      if ((e.target as HTMLElement)?.matches?.("input,select,textarea")) return;
      const k = e.key;
      if (k === "k" || k === "K") decide("kept");
      else if (k === "x" || k === "X" || k === "d" || k === "D") decide("discarded");
      else if (k === "ArrowRight" || k === "j") step(1);
      else if (k === "ArrowLeft") step(-1);
      else if (k === " ") { const v = vid.current; if (v) { if (v.paused) v.play(); else v.pause(); } }
      else if (k === "[") nudge("s", -2); else if (k === "]") nudge("s", 2);
      else if (k === ";") nudge("e", -2); else if (k === "'") nudge("e", 2);
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [reviewing, cam, decide, step, nudge]);

  const onTime = () => {
    const v = vid.current; if (!v || !pv) return;
    setProgress(Math.min(100, Math.max(0, ((v.currentTime - pv.start) / (pv.end - pv.start)) * 100)));
    if (v.currentTime >= pv.end) { v.currentTime = pv.start; if (!autoAdvance) v.pause(); }
  };

  // ---------------------------------------------------------------- chart
  useEffect(() => {
    const cv = chartRef.current; if (!cv || !job?.timeline.length) return;
    const dpr = window.devicePixelRatio || 1, W = cv.clientWidth, H = 64;
    cv.width = W * dpr; cv.height = H * dpr;
    const g = cv.getContext("2d")!; g.scale(dpr, dpr);
    const tl = job.timeline, max = Math.max(...tl, 1), span = job.window[1] - job.window[0], bw = W / tl.length;
    g.fillStyle = "#3a3448";
    tl.forEach((v, i) => { const h = Math.max(1.5, (v / max) * (H - 12)); g.fillRect(i * bw, H - h, Math.max(1, bw - (bw > 3 ? 1 : 0)), h); });
    for (const m of moments) {
      if (m.state === "discarded") continue;
      const x = (m.start / span) * W, w = Math.max(2, ((m.end - m.start) / span) * W);
      g.fillStyle = m.id === cur ? "#ff4f8b" : m.state === "kept" ? "#3ddc84" : "#ffffff30";
      g.fillRect(x, 0, w, m.id === cur || m.state === "kept" ? 7 : 3);
    }
  }, [job?.timeline, job?.window, moments, cur]);
  const chartClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!job) return;
    const t = (e.nativeEvent.offsetX / e.currentTarget.clientWidth) * (job.window[1] - job.window[0]);
    const pool = moments.filter(m => m.state !== "discarded");
    const m = pool.reduce<Moment | null>((b, c) => (!b || Math.abs((c.start + c.end) / 2 - t) < Math.abs((b.start + b.end) / 2 - t) ? c : b), null);
    if (!m) return;
    setTab(m.state as Tab); if (m.flag) setHideFlag(false);
    select(m.id);
  };

  // ---------------------------------------------------------------- kept clips
  const kept = moments.filter(m => m.state === "kept").sort((a, b) => a.start - b.start);
  const ready = kept.filter(m => m.status === "done").length;
  async function remake(m: Moment, rect?: Rect) {
    patchMoment(m.id, { status: "queued" });
    await api(`/api/projects/${id}/moments/${m.id}/recut`, { format: rect ? "vertical_facecam" : keptFmt, ...(rect ? { facecam_rect: rect } : {}) });
  }
  async function setSetting(vals: { format?: string; captions?: boolean }) {
    try { await api(`/api/projects/${id}/settings`, vals); }
    catch (caught) { const e = caught as ApiError; if (vals.captions !== undefined) setKeptCaps(false); say(e.message, e.upgrade); }
  }
  async function openCam(m: Moment) {
    setCam({ moment: m, rect: job?.facecam?.rect || null, all: true });
    try { const r = await api<{ url: string }>(`/api/projects/${id}/moments/${m.id}/frame`, {}); setCam(c => c && { ...c, url: r.url }); }
    catch (caught) { const e = caught as ApiError; setCam(c => c && { ...c, err: e.message }); }
  }
  const drag = useRef<{ x: number; y: number } | null>(null);
  const camPt = (e: React.PointerEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    return { x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)) };
  };
  async function saveCam() {
    if (!cam) return;
    const r = cam.rect; if (!r || r.w < 0.03 || r.h < 0.03) return say("Drag a box around the webcam first.");
    const rect = { x: +r.x.toFixed(4), y: +r.y.toFixed(4), w: +r.w.toFixed(4), h: +r.h.toFixed(4) };
    const targets = cam.all ? kept.filter(m => m.status === "done" && (m.format === "vertical_facecam" || m.id === cam.moment.id)) : [cam.moment];
    setCam({ ...cam, saving: true });
    try { for (const t of targets) await remake(t, rect); setCam(null); load(); }
    catch (caught) { const e = caught as ApiError; say(e.message); setCam(c => c && { ...c, saving: false }); }
  }

  async function del() {
    if (!window.confirm("Delete this project and all its clips? This can't be undone.")) return;
    try { await api(`/api/projects/${id}/delete`, {}); router.push("/app"); } catch (caught) { const e = caught as ApiError; say(e.message); }
  }

  // ---------------------------------------------------------------- render
  if (loadErr) return <div className="container app-page"><div className="empty-state card"><h2>{loadErr}</h2><Link className="btn btn-primary" href="/app">Back to projects</Link></div></div>;
  if (!job) return <div className="spinner-page"><div className="spin" /></div>;
  const m = byId(cur);
  const working = !["review", "done", "error", "cancelled"].includes(job.stage);

  return (
    <div className="container app-page" style={{ maxWidth: 1320 }}>
      <Link href="/app" className="muted" style={{ textDecoration: "none", fontSize: 14 }}>← All projects</Link>
      <div className="ws-head" style={{ marginTop: 10 }}>
        <div style={{ minWidth: 0 }}>
          <h1>{job.title || job.url}</h1>
          <div className="m">{[job.platform, job.uploader, job.window[1] > 0 ? `${fmtTime(job.window[1] - job.window[0])} scanned` : ""].filter(Boolean).join(" · ")}</div>
        </div>
        <div className="row">
          {working && <button className="btn btn-sm" onClick={() => api(`/api/projects/${id}/cancel`, {}).then(load).catch(e => say(e.message))}>Cancel scan</button>}
          <button className="btn btn-sm btn-ghost" onClick={del}>Delete project</button>
        </div>
      </div>

      {(working || job.stage === "error" || job.stage === "cancelled") && (
        <div className="card"><div className={`status ${job.stage === "error" ? "err" : ""}`}>{job.message}</div>
          {working && <div className="bar"><i style={{ width: `${Math.round(job.progress * 100)}%` }} /></div>}</div>
      )}
      {job.notes.map(n => <div key={n} className="note">{n}</div>)}

      {job.timeline.length > 0 && (
        <div className="chartwrap">
          <canvas id="chart" ref={chartRef} onClick={chartClick} aria-label="Action over time across the video" />
          <div className="lbl"><span>{fmtTime(job.window[0])}</span><span>Action over time · <span style={{ color: "#7ff0b0" }}>■</span> kept · <span style={{ color: "#ff8fb5" }}>■</span> playing · click to jump</span><span>{fmtTime(job.window[1])}</span></div>
        </div>
      )}

      {reviewing && (
        <div className="review" style={{ display: "grid" }}>
          <div className="stage">
            <div className="player">
              <video ref={vid} playsInline preload="auto" onTimeUpdate={onTime} onClick={() => { const v = vid.current; if (v) { if (v.paused) v.play(); else v.pause(); } }} />
              {m && <><div className="stamp">#{m.rank}</div><div className="stamp r">{Math.round(m.end - m.start)}s</div></>}
              {pvState !== "idle" && <div className="wait" style={{ display: "flex" }}>{pvState === "loading" ? <><div className="spin" /><span>Loading preview…</span></> : <span>{pvState}</span>}</div>}
              {!m && <div className="wait" style={{ display: "flex" }}><span>Nothing to review here.</span></div>}
            </div>
            <div className="scrub" onClick={e => { const v = vid.current; if (!v || !pv) return; const r = e.currentTarget.getBoundingClientRect();
              v.currentTime = pv.start + ((e.clientX - r.left) / r.width) * (pv.end - pv.start); v.play().catch(() => {}); }}><i style={{ width: `${progress}%` }} /></div>
            {m && (
              <div className="info">
                <div className="row" style={{ gap: 10 }}>
                  <span className="t">{m.label}</span>
                  <span className={`chip ${REASON_CLS[m.reason] ?? ""}`}>{m.reason}</span>
                  {m.flag && <span className="chip warn">{FLAG_TXT[m.flag]}</span>}
                  {m.state !== "new" && <span className={`chip ${m.state === "kept" ? "ok" : "warn"}`}>{m.state === "kept" ? "Kept" : "Discarded"}</span>}
                </div>
                <div className="row" style={{ gap: 6 }}><button className="btn btn-sm" onClick={() => step(-1)}>← Prev</button><button className="btn btn-sm" onClick={() => step(1)}>Next →</button></div>
              </div>
            )}
            <div className="decide">
              <button className="drop" onClick={() => decide("discarded")}>✕ Discard <kbd>X</kbd></button>
              <button className="keep" onClick={() => decide("kept")}>✓ Keep <kbd>K</kbd></button>
            </div>
            <div className="trimrow">
              <div className="g"><span>Start</span><button className="btn btn-sm" onClick={() => nudge("s", -2)}>−2s</button><button className="btn btn-sm" onClick={() => nudge("s", 2)}>+2s</button></div>
              <div className="g"><span>End</span><button className="btn btn-sm" onClick={() => nudge("e", -2)}>−2s</button><button className="btn btn-sm" onClick={() => nudge("e", 2)}>+2s</button></div>
              <label className="check" style={{ fontSize: 13 }}><input type="checkbox" checked={autoAdvance} onChange={e => setAutoAdvance(e.target.checked)} /> Auto-advance</label>
            </div>
            <div className="shortcuts"><span><kbd>K</kbd> keep</span><span><kbd>X</kbd> discard</span><span><kbd>←</kbd><kbd>→</kbd> prev / next</span><span><kbd>Space</kbd> play / pause</span><span><kbd>[</kbd><kbd>]</kbd> start −/+2s</span><span><kbd>;</kbd><kbd>&apos;</kbd> end −/+2s</span></div>
          </div>

          <aside className="side">
            <div className="top">
              <div className="tabs">
                {(["new", "kept", "discarded"] as Tab[]).map(t => (
                  <button key={t} className={tab === t ? "on" : ""} onClick={() => { setTab(t); const v = moments.filter(x => x.state === t); if (v.length && !v.some(x => x.id === cur)) setTimeout(() => select(v.sort((a, b) => a.rank - b.rank)[0].id), 0); }}>
                    {t === "new" ? "To review" : t === "kept" ? "Kept" : "Discarded"} ({counts[t]})</button>
                ))}
              </div>
              <div className="spread" style={{ gap: 6 }}>
                <div className="seg"><button className={sort === "best" ? "on" : ""} onClick={() => setSort("best")}>Best first</button><button className={sort === "time" ? "on" : ""} onClick={() => setSort("time")}>Timeline</button></div>
                <label className="check" style={{ fontSize: 12 }} title="Moments that look like menus, intermissions or full-screen camera">
                  <input type="checkbox" checked={hideFlag} onChange={e => setHideFlag(e.target.checked)} /> Hide non-gameplay {counts.flagged > 0 && <span className="muted">({counts.flagged})</span>}</label>
              </div>
            </div>
            <div className="list" ref={listRef}>
              {visible.length === 0 ? <div className="empty">{tab === "new" ? "Nothing left to review here. 🎉" : "None yet."}</div> :
                visible.map(x => (
                  <div key={x.id} data-id={x.id} className={`item ${x.state} ${x.id === cur ? "cur" : ""}`} role="button" tabIndex={0} onClick={() => select(x.id)}>
                    <span className="n">#{x.rank}</span>
                    <div><div className="tm">{x.label}</div><div className="sub">{Math.round(x.end - x.start)}s · {x.reason}{x.flag && <> · <span style={{ color: "#ff9a9a" }}>{FLAG_TXT[x.flag]}</span></>}</div></div>
                    <span className="st">{x.state === "kept" ? (x.status === "done" ? "✓" : "…") : ""}</span>
                  </div>
                ))}
            </div>
          </aside>
        </div>
      )}

      {kept.length > 0 && (
        <section className="kept card" style={{ display: "block" }}>
          <div className="kepthead">
            <h2>Kept clips <span className="muted" style={{ fontSize: 14, fontWeight: 500 }}>{ready} of {kept.length} ready</span></h2>
            <div className="row">
              <select value={keptFmt} onChange={e => { setKeptFmt(e.target.value); setSetting({ format: e.target.value }); }} title="Layout for new keeps">
                {Object.entries({ vertical_facecam: "9:16 webcam + gameplay", vertical_blur: "9:16 blurred fill", vertical_crop: "9:16 center crop", horizontal: "16:9 original" })
                  .map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <label className="check"><input type="checkbox" checked={keptCaps} disabled={!captionsAllowed} onChange={e => { setKeptCaps(e.target.checked); setSetting({ captions: e.target.checked }); }} /> Captions
                {!captionsAllowed && <Link className="lock" href="/pricing" style={{ textDecoration: "none" }}>🔒</Link>}</label>
              <button className="btn btn-primary btn-sm" disabled={!ready} onClick={() => downloadWithAuth(`/api/projects/${id}/kept.zip`, `${job.title.replace(/[^\w\- ]+/g, "").slice(0, 50) || "clips"} - kept clips.zip`).catch(e => say(e.message))}>Download all (.zip)</button>
            </div>
          </div>
          <p className="muted" style={{ fontSize: 13, margin: "-4px 0 14px" }}>Layout and captions apply to clips you keep from now on. Use “Re-make” to apply them to a clip you already kept.
            {job.watermark && <> Free plan exports include a small watermark. <Link href="/pricing" style={{ color: "var(--sun)" }}>Remove it</Link>.</>}</p>
          <div className="grid">
            {kept.map(k => {
              const busy = BUSY.includes(k.status);
              const vert = (k.format || "").startsWith("vertical");
              const wait = ({ queued: "Queued…", downloading: "Fetching HD…", captioning: "Writing captions…", rendering: "Making clip…" } as Record<string, string>)[k.status];
              return (
                <div key={k.id} className="clip">
                  <div className={`media ${vert ? "v" : "h"}`}>
                    {k.status === "done" && k.file_url ? <video controls preload="metadata" playsInline poster={k.thumb_url} src={k.file_url} />
                      : busy ? <div className="wait"><div className="spin" />{wait}</div>
                      : <div className="wait">{k.status === "error" ? "Couldn’t make this clip" : "Not made yet"}</div>}
                  </div>
                  <div className="body">
                    <div className="meta"><span className="time">{k.label}</span><span className="muted">{FMT[k.format || ""] || ""}{k.captioned ? " · CC" : ""}</span></div>
                    {k.error && <div className="cerr">{k.error}</div>}
                    <div className="actions">
                      <a className={`dl ${k.status === "done" ? "" : "off"}`} href={k.download_url || "#"}>Download</a>
                      <button disabled={busy} onClick={() => remake(k).catch(e => say(e.message))}>Re-make</button>
                      {k.format === "vertical_facecam" && <button disabled={busy} onClick={() => openCam(k)}>Webcam</button>}
                      <button title="Discard" aria-label="Discard clip" onClick={async () => { patchMoment(k.id, { state: "discarded" });
                        try { await api(`/api/projects/${id}/moments/${k.id}`, { state: "discarded" }); } catch (caught) { const e = caught as ApiError; say(e.message); load(); } }}>✕</button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {cam && (
        <div className="modal" style={{ display: "flex" }} role="dialog" aria-modal="true" aria-labelledby="cam-title">
          <div className="sheet">
            <h3 id="cam-title">Draw a box around the webcam</h3>
            <p className="muted" style={{ margin: "0 0 12px", fontSize: 14 }}>Click and drag on the frame. The box becomes the top part of the 9:16 webcam layout.</p>
            <div id="cam-stage"
              onPointerDown={e => { e.preventDefault(); drag.current = camPt(e); e.currentTarget.setPointerCapture(e.pointerId); }}
              onPointerMove={e => { if (!drag.current) return; const p = camPt(e), a = drag.current;
                setCam(c => c && { ...c, rect: { x: Math.min(a.x, p.x), y: Math.min(a.y, p.y), w: Math.abs(p.x - a.x), h: Math.abs(p.y - a.y) } }); }}
              onPointerUp={() => { drag.current = null; }}>
              {/* eslint-disable-next-line @next/next/no-img-element -- signed, short-lived URL */}
              {cam.url && <img src={cam.url} alt="Frame from the stream" draggable={false} />}
              {cam.rect && cam.url && <div id="cam-box" style={{ display: "block", left: `${cam.rect.x * 100}%`, top: `${cam.rect.y * 100}%`, width: `${cam.rect.w * 100}%`, height: `${cam.rect.h * 100}%` }} />}
              {!cam.url && <div id="cam-loading">{cam.err ? cam.err : <><div className="spin" />Grabbing a frame…</>}</div>}
            </div>
            <div className="spread" style={{ marginTop: 14 }}>
              <label className="check muted" style={{ fontSize: 14 }}><input type="checkbox" checked={cam.all} onChange={e => setCam({ ...cam, all: e.target.checked })} /> Re-make all kept webcam clips</label>
              <div className="row"><button className="btn" onClick={() => setCam(null)}>Cancel</button><button className="btn btn-primary" onClick={saveCam} disabled={cam.saving}>{cam.saving ? "Saving…" : "Use this box"}</button></div>
            </div>
          </div>
        </div>
      )}
      {toast && <div className="toast" style={{ display: "block" }} role="status">{toast.msg} {toast.upgrade && <Link href="/pricing">See plans →</Link>}</div>}
    </div>
  );
}
