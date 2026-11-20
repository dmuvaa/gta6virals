import Link from "next/link";

export default function NotFound() {
  return (
    <section className="section"><div className="container empty-state">
      <span className="eyebrow">404</span>
      <h1 style={{ fontSize: 44, fontWeight: 900 }}>This page went AFK</h1>
      <p>The page you&apos;re looking for doesn&apos;t exist or was moved.</p>
      <div className="row" style={{ justifyContent: "center" }}><Link className="btn btn-primary" href="/">Go home</Link></div>
    </div></section>
  );
}
