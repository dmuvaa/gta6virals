import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import JsonLd from "@/components/JsonLd";
import Faq from "@/components/Faq";
import { Breadcrumbs, CtaBand, Related, faqJsonLd, howToJsonLd } from "@/components/Seo";
import { TOOLS } from "@/lib/seo";
import { BRAND, SITE_URL } from "@/lib/site";

export const dynamicParams = false;
export function generateStaticParams() {
  return TOOLS.map(t => ({ slug: t.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const t = TOOLS.find(x => x.slug === slug);
  if (!t) return {};
  return {
    title: { absolute: `${t.metaTitle} · ${BRAND}` }, description: t.description,
    alternates: { canonical: `/tools/${t.slug}` },
    openGraph: { title: t.metaTitle, description: t.description, url: `/tools/${t.slug}` },
    twitter: { title: t.metaTitle, description: t.description },
  };
}

export default async function ToolPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const t = TOOLS.find(x => x.slug === slug);
  if (!t) notFound();
  return (
    <>
      <JsonLd data={{ "@context": "https://schema.org", "@type": "SoftwareApplication", name: `${BRAND}: ${t.title}`,
        applicationCategory: "MultimediaApplication", operatingSystem: "Web", url: `${SITE_URL}/tools/${t.slug}`, description: t.description,
        offers: { "@type": "Offer", price: "0", priceCurrency: "USD" } }} />
      <JsonLd data={howToJsonLd(`How to use the ${t.title.toLowerCase()}`, t.description, t.steps)} />
      <JsonLd data={faqJsonLd(t.faq)} />

      <section className="seo-hero">
        <div className="container">
          <Breadcrumbs items={[["Tools", "/gta-6-clips"], [t.title, `/tools/${t.slug}`]]} />
          <span className="pill"><span className="dot" /> {t.eyebrow}</span>
          <h1>{t.h1}</h1>
          <p className="lead">{t.lead}</p>
          <div className="hero-ctas">
            <Link className="btn btn-primary btn-lg" href="/signup">Try it free</Link>
            <Link className="btn btn-outline btn-lg" href="/pricing">See pricing</Link>
          </div>
          <div className="trust"><span>Free plan</span><span>No credit card</span><span>YouTube &amp; Twitch</span></div>
        </div>
      </section>

      <section className="block"><div className="container">
        <div className="grid-3">{t.benefits.map(([h, p]) => <div key={h} className="card mini"><h3>{h}</h3><p>{p}</p></div>)}</div>
      </div></section>

      <section className="block"><div className="container article">
        <h2>How it works</h2>
        <ol className="numbered">{t.steps.map(([h, p]) => <li key={h}><b>{h}</b>{p}</li>)}</ol>
      </div></section>

      {t.body.map(s => (
        <section key={s.h} className="block"><div className="container article">
          <h2>{s.h}</h2>{s.p.map((p, i) => <p key={i}>{p}</p>)}
        </div></section>
      ))}

      <section className="block"><div className="container">
        <div className="article"><h2>Questions</h2></div>
        <div style={{ marginTop: 18 }}><Faq items={t.faq} openFirst /></div>
      </div></section>

      <Related keys={t.related} title="Related" />
      <CtaBand title={t.cta[0]} text={t.cta[1]} />
    </>
  );
}
