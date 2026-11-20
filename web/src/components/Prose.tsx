export default function Prose({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <article className="prose">
      <h1>{title}</h1>
      <p className="updated">Last updated: November 20, 2026</p>
      <div className="notice">Draft for review: have a lawyer check this page before launch.</div>
      {children}
    </article>
  );
}
