"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { createClient } from "@/utils/supabase/client";
import { BRAND } from "@/lib/site";

export function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="18" height="18"><path d="M8 5v14l11-7z" fill="currentColor" /></svg>
    </span>
  );
}

type NavUser = { email: string; name: string } | null;

export default function Navbar({ user }: { user: NavUser }) {
  const path = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const inApp = path.startsWith("/app");
  useEffect(() => setOpen(false), [path]);
  useEffect(() => { document.body.classList.toggle("nav-open", open); }, [open]);
  useEffect(() => { document.body.classList.toggle("app-body", inApp); }, [inApp]);

  const links = inApp
    ? [["/app", "Projects"], ["/app/new", "New project"], ["/app/account", "Account"]]
    : [["/#features", "Features"], ["/gta-6-clips", "GTA 6 clips"], ["/pricing", "Pricing"], ["/faq", "FAQ"]];
  const isCurrent = (href: string) => (href === "/app" ? path === "/app" || path.startsWith("/app/p/") : path === href);

  async function logout() {
    await createClient().auth.signOut();
    router.push("/");
    router.refresh();
  }

  return (
    <header className="nav">
      <div className="container nav-inner">
        <Link className="brand" href={user && inApp ? "/app" : "/"} aria-label={`${BRAND} home`}>
          <BrandMark /><span>{BRAND}</span>
        </Link>
        <nav className="nav-links" id="nav-links" aria-label={inApp ? "App" : "Main"}>
          {links.map(([href, label]) => (
            <Link key={href} href={href} aria-current={isCurrent(href) ? "page" : undefined}>{label}</Link>
          ))}
        </nav>
        <div className="nav-cta">
          {user ? (
            <>
              {!inApp && <Link className="btn btn-primary btn-sm" href="/app">Open dashboard</Link>}
              <details className="menu">
                <summary aria-label="Account menu"><span className="avatar">{(user.name || user.email)[0]?.toUpperCase()}</span></summary>
                <div className="menu-pop">
                  <div className="menu-head"><strong>{user.name || "Your account"}</strong><span>{user.email}</span></div>
                  <Link href="/app">Dashboard</Link>
                  <Link href="/app/new">New project</Link>
                  <Link href="/app/account">Account &amp; billing</Link>
                  <button type="button" onClick={logout}>Log out</button>
                </div>
              </details>
            </>
          ) : (
            <>
              <Link className="btn btn-ghost btn-sm" href="/login">Log in</Link>
              <Link className="btn btn-primary btn-sm" href="/signup">Start free</Link>
            </>
          )}
          <button className="nav-toggle" aria-label="Open menu" aria-expanded={open} aria-controls="nav-links" onClick={() => setOpen(o => !o)}>
            <span /><span />
          </button>
        </div>
      </div>
    </header>
  );
}
