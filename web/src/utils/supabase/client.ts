import { createBrowserClient } from "@supabase/ssr";

/** Supabase client for Client Components (runs in the browser). */
export const createClient = () =>
  createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
  );
