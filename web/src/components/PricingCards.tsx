"use client";
import Link from "next/link";
import Script from "next/script";
import { useEffect, useState } from "react";
import { createClient } from "@/utils/supabase/client";
import { PADDLE, PLANS, SITE_URL, billingEnabled } from "@/lib/site";

type PaddleJs = {
  Initialized?: boolean;
  Environment: { set(env: string): void };
  Initialize(opts: { token: string }): void;
  Checkout: { open(opts: Record<string, unknown>): void };
};
declare global { interface Window { Paddle?: PaddleJs } }

export default function PricingCards() {
  const [user, setUser] = useState<{ id: string; email: string } | null>(null);
  const [currentPlan, setCurrentPlan] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const live = billingEnabled();

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user) return;
      setUser({ id: user.id, email: user.email || "" });
      const { data } = await supabase.from("profiles").select("plan").eq("id", user.id).single();
      setCurrentPlan(data?.plan || "free");
    });
  }, []);

  function upgrade(planKey: string) {
    const P = window.Paddle;
    if (!P || !user) return;
    setBusy(planKey);
    try {
      if (PADDLE.env !== "production") P.Environment.set("sandbox");
      if (!P.Initialized) P.Initialize({ token: PADDLE.token });
      P.Checkout.open({
        items: [{ priceId: PADDLE.prices[planKey], quantity: 1 }],
        customer: { email: user.email },
        customData: { user_id: user.id },
        settings: { successUrl: `${SITE_URL}/app/account?upgraded=1`, displayMode: "overlay", theme: "dark" },
      });
    } finally { setTimeout(() => setBusy(null), 1500); }
  }

  return (
    <>
      {live && user && <Script src="https://cdn.paddle.com/paddle/v2/paddle.js" strategy="lazyOnload" />}
      <div className="price-grid">
        {PLANS.map(p => {
          const featured = p.key === "creator";
          const cls = `btn ${featured ? "btn-primary" : "btn-outline"} btn-block`;
          let cta;
          if (p.key === "free") cta = user
            ? <Link className="btn btn-outline btn-block" href="/app">{currentPlan === "free" ? "Your current plan" : "Go to dashboard"}</Link>
            : <Link className="btn btn-outline btn-block" href="/signup">Start free</Link>;
          else if (user && currentPlan === p.key) cta = <Link className="btn btn-outline btn-block" href="/app/account">Your current plan</Link>;
          else if (user) cta = <button type="button" className={cls} disabled={!live || busy === p.key} onClick={() => upgrade(p.key)}>
            {live ? `Upgrade to ${p.name}` : `${p.name}: coming soon`}</button>;
          else cta = <Link className={cls} href="/signup?next=/pricing">Get {p.name}</Link>;
          return (
            <div key={p.key} className={`card price ${featured ? "featured" : ""}`}>
              {featured && <span className="badge">Most popular</span>}
              <div>
                <h3>{p.name}</h3>
                <div className="amt"><b>${p.price}</b><span>/ month</span></div>
                <p className="blurb">{p.blurb}</p>
              </div>
              <ul>{p.features.map(f => <li key={f}>{f}</li>)}</ul>
              {cta}
            </div>
          );
        })}
      </div>
      {!live && <p className="muted" style={{ textAlign: "center", marginTop: 18, fontSize: 14 }}>Paid plans open soon. Start free today, and upgrade when billing goes live.</p>}
    </>
  );
}
