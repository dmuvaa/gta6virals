import Link from "next/link";
import JsonLd from "./JsonLd";
import { SITE_URL } from "@/lib/site";
import { RELATED, type RelatedKey } from "@/lib/seo";

/** Visible breadcrumbs plus BreadcrumbList structured data. */
export function Breadcrumbs({ items }: { items: [string, string][] }) {
  const all: [string, string][] = [["Home", "/"], ...items];
  return (
    <>
      <JsonLd data={{ "@context": "https://schema.org", "@type": "BreadcrumbList",
        itemListElement: all.map(([name, href], i) => ({ "@type": "ListItem", position: i + 1, name, item: `${SITE_URL}${href}` })) }} />
      <nav className="crumbs" aria-label="Breadcrumb">
        {all.map(([name, href], i) => (
          <span key={href} style={{ display: "contents" }}>
            {i > 0 && <span aria-hidden="true">/</span>}
            {i < all.length - 1 ? <Link href={href}>{name}</Link> : <span aria-current="page">{name}</span>}
          </span>
        ))}
      </nav>
    </>
  );
}

export function CtaBand({ title, text, cta = "Start clipping free" }: { title: string; text: string; cta?: string }) {
  return (
    <section className="section-tight"><div className="container"><div className="cta-band">
      <h2>{title}</h2><p>{text}</p>
      <Link className="btn btn-primary btn-lg" href="/signup">{cta}</Link>
      <p className="muted" style={{ fontSize: 14, marginTop: 14 }}>Free plan · No credit card · 3 hours of video every month</p>
    </div></div></section>
  );
}

export function Related({ keys, title = "Keep reading" }: { keys: RelatedKey[]; title?: string }) {
  return (
    <section className="block"><div className="container">
      <h2 style={{ fontSize: 26, fontWeight: 900, marginBottom: 16 }}>{title}</h2>
      <div className="related">
        {keys.map(k => <Link key={k} href={RELATED[k].href}><b>{RELATED[k].title}</b><span>{RELATED[k].text}</span></Link>)}
      </div>
    </div></section>
  );
}

export function faqJsonLd(items: [string, string][]) {
  return { "@context": "https://schema.org", "@type": "FAQPage",
    mainEntity: items.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })) };
}

export function howToJsonLd(name: string, description: string, steps: [string, string][]) {
  return { "@context": "https://schema.org", "@type": "HowTo", name, description,
    step: steps.map(([n, t], i) => ({ "@type": "HowToStep", position: i + 1, name: n, text: t })) };
}
