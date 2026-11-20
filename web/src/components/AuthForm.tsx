"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { createClient } from "@/utils/supabase/client";
import { BRAND, SITE_URL } from "@/lib/site";

const PROVIDERS = (process.env.NEXT_PUBLIC_AUTH_PROVIDERS || "").split(",").map(s => s.trim()).filter(Boolean) as ("google" | "twitch" | "discord")[];
const LABEL: Record<string, string> = { google: "Google", twitch: "Twitch", discord: "Discord" };

function safeNext(n: string | null) {
  return n && n.startsWith("/") && !n.startsWith("//") ? n : "/app";
}

export default function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [agree, setAgree] = useState(false);
  const [error, setError] = useState(params.get("error") ? "That link has expired or was already used. Please try again." : "");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const supabase = createClient();
  const callback = `${SITE_URL}/auth/callback?next=${encodeURIComponent(next)}`;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setNotice("");
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return setError("Enter a valid email address.");
    if (mode === "signup") {
      if (password.length < 8) return setError("Use a password with at least 8 characters.");
      if (!agree) return setError("Please accept the Terms and Privacy Policy.");
    }
    setBusy(true);
    if (mode === "login") {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      setBusy(false);
      if (error) return setError(error.message.includes("Email not confirmed")
        ? "Please confirm your email first. Check your inbox for the link."
        : "That email and password don't match.");
      router.push(next); router.refresh();
    } else {
      const { data, error } = await supabase.auth.signUp({ email, password,
        options: { data: { name: name.trim() }, emailRedirectTo: callback } });
      setBusy(false);
      if (error) return setError(error.message);
      if (data.session) { router.push(next); router.refresh(); }
      else setNotice(`Almost there! We sent a confirmation link to ${email}. Click it to finish creating your account.`);
    }
  }

  async function oauth(provider: "google" | "twitch" | "discord") {
    setError("");
    const { error } = await supabase.auth.signInWithOAuth({ provider, options: { redirectTo: callback } });
    if (error) setError(error.message);
  }

  return (
    <div className="auth-wrap"><div className="auth card" style={{ padding: 32 }}>
      <h1>{mode === "login" ? "Welcome back" : "Create your account"}</h1>
      <p className="sub">{mode === "login" ? `Log in to your ${BRAND} account` : "Free plan · No credit card needed"}</p>
      {PROVIDERS.length > 0 && <>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {PROVIDERS.map(p => <button key={p} type="button" className="btn btn-oauth btn-block" onClick={() => oauth(p)}>Continue with {LABEL[p] || p}</button>)}
        </div>
        <div className="divider">or with email</div>
      </>}
      <form onSubmit={submit} noValidate>
        {mode === "signup" && <label className="field">Name <input value={name} onChange={e => setName(e.target.value)} autoComplete="name" maxLength={80} /></label>}
        <label className="field">Email <input type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" required autoFocus={mode === "login"} /></label>
        <label className="field">Password <input type="password" value={password} onChange={e => setPassword(e.target.value)}
          autoComplete={mode === "login" ? "current-password" : "new-password"} placeholder={mode === "signup" ? "At least 8 characters" : undefined} required /></label>
        {mode === "signup" && <label className="check" style={{ fontSize: 13, color: "var(--muted)" }}>
          <input type="checkbox" checked={agree} onChange={e => setAgree(e.target.checked)} /> I agree to the <Link href="/legal/terms" target="_blank">Terms</Link> and <Link href="/legal/privacy" target="_blank">Privacy Policy</Link>
        </label>}
        {error && <div className="form-error" role="alert">{error}</div>}
        {notice && <div className="form-ok" role="status">{notice}</div>}
        <button className="btn btn-primary btn-block btn-lg" type="submit" disabled={busy}>
          {busy ? "One moment…" : mode === "login" ? "Log in" : "Create account"}</button>
      </form>
      {mode === "login" ? <>
        <p className="alt"><Link href="/forgot-password">Forgot your password?</Link></p>
        <p className="alt" style={{ marginTop: 8 }}>New here? <Link href={`/signup${next !== "/app" ? `?next=${encodeURIComponent(next)}` : ""}`}>Create a free account</Link></p>
      </> : <p className="alt">Already have an account? <Link href={`/login${next !== "/app" ? `?next=${encodeURIComponent(next)}` : ""}`}>Log in</Link></p>}
    </div></div>
  );
}
