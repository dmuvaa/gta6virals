"use client";
import Link from "next/link";
import { useState } from "react";
import { createClient } from "@/utils/supabase/client";
import { SITE_URL } from "@/lib/site";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError(""); setBusy(true);
    const { error } = await createClient().auth.resetPasswordForEmail(email, {
      redirectTo: `${SITE_URL}/auth/callback?next=/reset-password` });
    setBusy(false);
    if (error) setError(error.message); else setSent(true);
  }
  return (
    <div className="auth-wrap"><div className="auth card" style={{ padding: 32 }}>
      <h1>Reset your password</h1>
      <p className="sub">We&apos;ll email you a link to choose a new one.</p>
      {sent ? <div className="form-ok">If an account exists for {email}, a reset link is on its way. Check your inbox (and spam).</div> :
      <form onSubmit={submit}>
        <label className="field">Email <input type="email" value={email} onChange={e => setEmail(e.target.value)} required autoFocus autoComplete="email" /></label>
        {error && <div className="form-error">{error}</div>}
        <button className="btn btn-primary btn-block btn-lg" disabled={busy}>{busy ? "Sending…" : "Send reset link"}</button>
      </form>}
      <p className="alt"><Link href="/login">Back to log in</Link></p>
    </div></div>
  );
}
