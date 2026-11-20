"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { createClient } from "@/utils/supabase/client";

export default function ResetPassword() {
  const router = useRouter();
  const [pw, setPw] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError("");
    if (pw.length < 8) return setError("Use a password with at least 8 characters.");
    setBusy(true);
    const { error } = await createClient().auth.updateUser({ password: pw });
    setBusy(false);
    if (error) return setError(error.message.includes("session") ? "This reset link has expired. Request a new one." : error.message);
    router.push("/app"); router.refresh();
  }
  return (
    <div className="auth-wrap"><div className="auth card" style={{ padding: 32 }}>
      <h1>Choose a new password</h1>
      <p className="sub">At least 8 characters.</p>
      <form onSubmit={submit}>
        <label className="field">New password <input type="password" value={pw} onChange={e => setPw(e.target.value)} autoComplete="new-password" required autoFocus /></label>
        {error && <div className="form-error">{error}</div>}
        <button className="btn btn-primary btn-block btn-lg" disabled={busy}>{busy ? "Saving…" : "Save password"}</button>
      </form>
    </div></div>
  );
}
