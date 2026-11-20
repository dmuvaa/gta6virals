"use client";
import { createClient } from "@/utils/supabase/client";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765").replace(/\/$/, "");

export class ApiError extends Error {
  status: number; upgrade?: boolean;
  constructor(message: string, status: number, upgrade?: boolean) { super(message); this.status = status; this.upgrade = upgrade; }
}

/** Call the Python API with the user's Supabase access token. */
export async function api<T = unknown>(path: string, body?: unknown, method?: string): Promise<T> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) {
    window.location.href = `/login?next=${encodeURIComponent(location.pathname)}`;
    throw new ApiError("Please log in.", 401);
  }
  const r = await fetch(API + path, {
    method: method || (body === undefined ? "GET" : "POST"),
    headers: { Authorization: `Bearer ${session.access_token}`, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (r.status === 401) {
    window.location.href = `/login?next=${encodeURIComponent(location.pathname)}`;
    throw new ApiError("Please log in.", 401);
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(data.error || `Something went wrong (${r.status}).`, r.status, data.upgrade);
  return data as T;
}

/** Download a file that needs the auth header (e.g. the .zip of kept clips). */
export async function downloadWithAuth(path: string, filename: string) {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  const r = await fetch(API + path, { headers: { Authorization: `Bearer ${session?.access_token}` } });
  if (!r.ok) { const d = await r.json().catch(() => ({})); throw new ApiError(d.error || "Download failed.", r.status); }
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}
