"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Me, ProjectSummary } from "@/lib/types";

const WORKING = ["queued", "probing", "downloading", "analyzing"];
const ago = (iso: string) => {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)}m ago` : s < 86400 ? `${Math.floor(s / 3600)}h ago` : `${Math.floor(s / 86400)}d ago`;
};

export default function Dashboard() {
  const [me, setMe] = useState<Me | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "Dashboard · Hypecut";
    let t: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const [m, p] = await Promise.all([api<Me>("/api/me"), api<ProjectSummary[]>("/api/projects")]);
        setMe(m); setProjects(p); setError("");
        if (p.some(x => WORKING.includes(x.stage))) t = setTimeout(load, 3000);
      } catch (caught) { const e = caught as ApiError; setError(e.message); }
    };
    load();
    return () => clearTimeout(t);
  }, []);

  if (error) return <div className="container app-page"><div className="form-error">{error}</div></div>;
  if (!me || !projects) return <div className="spinner-page"><div className="spin" /></div>;
  const hp = Math.min(100, Math.round((me.usage.hours / me.limits.hours) * 100));
  const ep = Math.min(100, Math.round((me.usage.exports / me.limits.exports) * 100));
  const ready = projects.reduce((n, p) => n + p.counts.ready, 0);

  return (
    <div className="container app-page">
      <div className="page-head">
        <div><h1>Your projects</h1><p>Hi{me.name ? ` ${me.name}` : ""}! Paste a stream to find its best moments.</p></div>
        <Link className="btn btn-primary" href="/app/new">+ New project</Link>
      </div>
      <div className="kpis">
        <div className="card kpi"><div className="lbl">Plan</div><div className="val">{me.limits.name}</div>
          {me.plan === "free" ? <Link href="/pricing" style={{ fontSize: 13, color: "var(--sun)", fontWeight: 600 }}>Upgrade for captions &amp; more hours →</Link>
            : <Link href="/app/account" style={{ fontSize: 13, color: "var(--muted)" }}>Manage plan</Link>}</div>
        <div className="card kpi"><div className="lbl">Video scanned this month</div>
          <div className="val">{me.usage.hours.toFixed(1)} <small>/ {me.limits.hours} h</small></div>
          <div className={`meter ${hp >= 90 ? "warn" : ""}`}><i style={{ width: `${hp}%` }} /></div></div>
        <div className="card kpi"><div className="lbl">Clips exported this month</div>
          <div className="val">{me.usage.exports} <small>/ {me.limits.exports.toLocaleString()}</small></div>
          <div className={`meter ${ep >= 90 ? "warn" : ""}`}><i style={{ width: `${ep}%` }} /></div></div>
        <div className="card kpi"><div className="lbl">Clips ready to download</div><div className="val">{ready}</div>
          <div className="lbl" style={{ marginTop: 6 }}>across {projects.length} project{projects.length === 1 ? "" : "s"}</div></div>
      </div>
      {projects.length ? (
        <div className="projects">
          {projects.map(p => (
            <Link key={p.id} className="card proj" href={`/app/p/${p.id}`}>
              <div className="thumb" style={p.thumbnail ? { backgroundImage: `url('${p.thumbnail}')` } : undefined}>
                <span className="st">{["review", "done"].includes(p.stage) ? <span className="chip ok">Ready</span>
                  : p.stage === "error" ? <span className="chip warn">Failed</span>
                  : p.stage === "cancelled" ? <span className="chip dark">Cancelled</span>
                  : <span className="chip a">Scanning… {Math.round(p.progress * 100)}%</span>}</span>
              </div>
              <div className="info">
                <div className="t">{p.title || p.url}</div>
                <div className="m">{[p.platform, p.uploader].filter(Boolean).join(" · ")}</div>
                <div className="nums">
                  {p.counts.moments > 0 && <span><b>{p.counts.moments}</b> moments</span>}
                  <span><b>{p.counts.kept}</b> kept</span><span>{ago(p.created_at)}</span>
                </div>
                {p.stage === "error" && <div className="m" style={{ color: "var(--bad)" }}>{p.message}</div>}
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="card empty-state">
          <div className="icon" style={{ width: 56, height: 56 }}><svg viewBox="0 0 24 24"><path fill="currentColor" d="M8 5v14l11-7z" /></svg></div>
          <h2>No projects yet</h2>
          <p>Paste a YouTube or Twitch link to a stream. We&apos;ll scan it and line up every moment with action for you to review.</p>
          <Link className="btn btn-primary" href="/app/new">Start your first project</Link>
        </div>
      )}
    </div>
  );
}
