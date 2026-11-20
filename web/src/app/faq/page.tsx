import type { Metadata } from "next";
import Link from "next/link";
import JsonLd from "@/components/JsonLd";
import Faq from "@/components/Faq";
import { BRAND, FAQ, SUPPORT_EMAIL } from "@/lib/site";

export const metadata: Metadata = { title: "FAQ", description: `Answers to common questions about ${BRAND}.`, alternates: { canonical: "/faq" } };

export default function FaqPage() {
  return (
    <>
      <JsonLd data={{ "@context": "https://schema.org", "@type": "FAQPage",
        mainEntity: FAQ.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })) }} />
      <section className="section">
        <div className="container">
          <div className="section-head"><span className="eyebrow">FAQ</span>
            <h1 style={{ fontSize: "clamp(34px,5vw,52px)", fontWeight: 900 }}>Frequently asked questions</h1>
            <p>Can&apos;t find what you need? Email <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.</p></div>
          <Faq items={FAQ} openFirst />
        </div>
      </section>
      <section className="section-tight"><div className="container"><div className="cta-band">
        <h2>Ready to find your best moments?</h2><p>Start free. No credit card needed.</p>
        <Link className="btn btn-primary btn-lg" href="/signup">Start clipping free</Link>
      </div></div></section>
    </>
  );
}
