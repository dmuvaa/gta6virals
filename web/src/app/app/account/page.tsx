"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";
import type { Me } from "@/lib/types";

function Account() {
  const router = useRouter();
  const params = useSearchParams();
  const [me, setMe] = useState<Me | null>(null);
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    document.title = "Account · Hypecut";
    const load = () => api<Me>("/api/me").then(setMe).catch(e => setMsg({ err: e.message }));
    load();
    // After checkout, Paddle's webhook upgrades the plan a few seconds later.
    if (params.get("upgraded")) { const t = setInterval(load, 3000); setTimeout(() => clearInterval(t), 30000); return () => clearInterval(t); }
  }, [params]);

  async function portal() {
    setBusy("portal");
    try { const r = await api<{ url: string }>("/api/billing/portal", {}); window.location.href = r.url; }
    catch (caught) { const e = caught as ApiError; setMsg({ err: e.message }); setBusy(""); }
  }
  async function changePassword(e: React.FormEvent) {
    e.preventDefault(); setMsg({});
    if (pw.length < 8) return setMsg({ err: "Use a password with at least 8 characters." });
    setBusy("pw");
    const { error } = await createClient().auth.updateUser({ password: pw });
    setBusy("");
    if (error) setMsg({ err: error.message }); else { setPw(""); setMsg({ ok: "Password updated." }); }
  }
  async function deleteAccount(e: React.FormEvent) {
    e.preventDefault();
    if (!me || confirm.trim().toLowerCase() !== me.email.toLowerCase()) return setMsg({ err: "Type your email to confirm." });
    if (!window.confirm("Delete your account and everything in it? This cannot be undone.")) return;
    setBusy("del");
    try {
      await api("/api/account/delete", {});
      await createClient().auth.signOut();
      router.push("/"); router.refresh();
    } catch (caught) { const e = caught as ApiError; setMsg({ err: e.message }); setBusy(""); }
  }

  if (!me) return msg.err ? <div className="container app-page"><div className="form-error">{msg.err}</div></div> : <div className="spinner-page"><div className="spin" /></div>;
  const L = me.limits;
  const hp = Math.min(100, Math.round((me.usage.hours / L.hours) * 100));
  const ep = Math.min(100, Math.round((me.usage.exports / L.exports) * 100));

  return (
    <div className="container app-page">
      <div className="page-head"><div><h1>Account</h1><p>Manage your plan, password and data.</p></div></div>
      {params.get("upgraded") && <div className="form-ok" style={{ marginBottom: 18 }}>Thanks for upgrading! Your plan updates as soon as payment is confirmed (usually a few seconds).</div>}
      {msg.err && <div className="form-error" style={{ marginBottom: 18 }}>{msg.err}</div>}
      {msg.ok && <div className="form-ok" style={{ marginBottom: 18 }}>{msg.ok}</div>}
      <div className="settings">
        <nav aria-label="Account sections"><a href="#plan">Plan &amp; usage</a><a href="#profile">Profile</a><a href="#password">Password</a><a href="#danger">Delete account</a></nav>
        <div>
          <section className="card" id="plan">
            <div className="spread">
              <div><h2>{L.name} plan</h2>
                <p className="muted" style={{ fontSize: 14 }}>{L.price ? `$${L.price}/month` : "Free forever"}{me.plan_status && me.plan_status !== "active" ? ` · status: ${me.plan_status}` : ""} · limits reset on the 1st of each month</p></div>
              {me.plan === "free" ? <Link className="btn btn-primary btn-sm" href="/pricing">Upgrade</Link>
                : me.has_billing && <button className="btn btn-sm" onClick={portal} disabled={busy === "portal"}>{busy === "portal" ? "Opening…" : "Manage billing"}</button>}
            </div>
            <div className="form-grid" style={{ marginTop: 18 }}>
              <div><div className="spread" style={{ fontSize: 14 }}><span className="muted">Video scanned</span><b>{me.usage.hours.toFixed(1)} / {L.hours} h</b></div>
                <div className={`meter ${hp >= 90 ? "warn" : ""}`}><i style={{ width: `${hp}%` }} /></div></div>
              <div><div className="spread" style={{ fontSize: 14 }}><span className="muted">Clips exported</span><b>{me.usage.exports} / {L.exports.toLocaleString()}</b></div>
                <div className={`meter ${ep >= 90 ? "warn" : ""}`}><i style={{ width: `${ep}%` }} /></div></div>
            </div>
            <p className="muted" style={{ fontSize: 13, marginTop: 14 }}>Captions: {L.captions ? "included" : "not included"} · Watermark: {L.watermark ? "yes" : "none"} · Longest video: {L.max_video_hours} hours</p>
          </section>

          <section className="card" id="profile">
            <h2>Profile</h2><p>Your login email.</p>
            <div className="form-grid"><label className="field">Name <input value={me.name} disabled /></label><label className="field">Email <input value={me.email} disabled /></label></div>
          </section>

          <section className="card" id="password">
            <h2>Password</h2><p>Use at least 8 characters. If you signed up with Google or Twitch, this adds a password login too.</p>
            <form onSubmit={changePassword} className="row">
              <input type="password" value={pw} onChange={e => setPw(e.target.value)} placeholder="New password" autoComplete="new-password" style={{ maxWidth: 320 }} />
              <button className="btn btn-sm" disabled={busy === "pw"}>{busy === "pw" ? "Saving…" : "Update password"}</button>
            </form>
          </section>

          <section className="card" id="danger" style={{ borderColor: "#ff5d5d44" }}>
            <h2>Delete account</h2>
            <p>Permanently deletes your account, all projects and all clips. This can&apos;t be undone.{me.plan !== "free" ? " Cancel your subscription under Manage billing first, so you aren't charged again." : ""}</p>
            <form onSubmit={deleteAccount} className="row">
              <input value={confirm} onChange={e => setConfirm(e.target.value)} placeholder={`Type ${me.email} to confirm`} style={{ maxWidth: 340 }} autoComplete="off" />
              <button className="btn btn-danger btn-sm" disabled={busy === "del"}>{busy === "del" ? "Deleting…" : "Delete account"}</button>
            </form>
          </section>
        </div>
      </div>
    </div>
  );
}

export default function AccountPage() {
  return <Suspense fallback={<div className="spinner-page"><div className="spin" /></div>}><Account /></Suspense>;
}
