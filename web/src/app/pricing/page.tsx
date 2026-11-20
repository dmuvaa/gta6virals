import type { Metadata } from "next";
import JsonLd from "@/components/JsonLd";
import Faq from "@/components/Faq";
import PricingCards from "@/components/PricingCards";
import { BRAND, FAQ, PLANS, SITE_URL } from "@/lib/site";

export const metadata: Metadata = {
  title: "Pricing",
  description: `Start free. ${BRAND} Creator and Pro plans for clippers who post every day.`,
  alternates: { canonical: "/pricing" },
};

const ROWS: [string, (p: (typeof PLANS)[number]) => string][] = [
  ["Hours of video per month", p => String(p.hours)],
  ["HD clip exports per month", p => p.exports.toLocaleString()],
  ["Longest video per project", p => `${p.maxVideoHours} hours`],
  ["Burned-in captions", p => (p.captions ? "✓" : "—")],
  ["No watermark", p => (p.watermark ? "—" : "✓")],
  ["9:16 webcam, blur and crop layouts", () => "✓"],
  ["Webcam auto-detect", () => "✓"],
  ["Non-gameplay flagging", () => "✓"],
  ["Download all as .zip", () => "✓"],
  ["Priority processing", p => (p.key === "pro" ? "✓" : "—")],
];

export default function Pricing() {
  return (
    <>
      <JsonLd data={{ "@context": "https://schema.org", "@type": "Product", name: BRAND,
        offers: PLANS.map(p => ({ "@type": "Offer", name: p.name, price: String(p.price), priceCurrency: "USD", url: `${SITE_URL}/pricing` })) }} />
      <section className="hero" style={{ paddingBottom: 40 }}>
        <div className="container">
          <div className="section-head" style={{ marginBottom: 40 }}>
            <span className="eyebrow">Pricing</span>
            <h1 style={{ fontSize: "clamp(36px,5vw,56px)", fontWeight: 900 }}>Pay for the hours you clip</h1>
            <p>Every plan includes the full review workflow, all layouts and webcam auto-detect. Upgrade for more hours, captions and no watermark.</p>
          </div>
          <PricingCards />
        </div>
      </section>
      <section className="section-tight">
        <div className="container">
          <h2 style={{ fontSize: 28, fontWeight: 900, marginBottom: 20, textAlign: "center" }}>Compare plans</h2>
          <div className="table-wrap">
            <table className="compare">
              <thead><tr><th>Feature</th>{PLANS.map(p => <th key={p.key}>{p.name}</th>)}</tr></thead>
              <tbody>{ROWS.map(([label, f]) => <tr key={label}><td>{label}</td>{PLANS.map(p => <td key={p.key}>{f(p)}</td>)}</tr>)}</tbody>
            </table>
          </div>
        </div>
      </section>
      <section className="section-tight">
        <div className="container">
          <h2 style={{ fontSize: 28, fontWeight: 900, marginBottom: 20, textAlign: "center" }}>Billing questions</h2>
          <Faq items={[
            ["What counts as an hour of video?", "The length of video we scan. A full 12-hour stream uses 12 hours. Scan just 9:00:00–11:00:00 of it and it uses 2. Unused hours don't roll over."],
            ["What counts as an export?", "Each moment you keep and we make in HD. Re-making a clip you already kept (new trim, layout or webcam box) is free."],
            ["Who handles payments?", "Our reseller and merchant of record, Paddle, handles checkout, invoices and sales tax. You can manage or cancel your subscription anytime from your account page."],
            ...FAQ.slice(4),
          ]} />
        </div>
      </section>
    </>
  );
}
