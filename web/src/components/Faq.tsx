export default function Faq({ items, openFirst = false }: { items: [string, string][]; openFirst?: boolean }) {
  return (
    <div className="faq">
      {items.map(([q, a], i) => (
        <details key={q} open={openFirst && i === 0}><summary>{q}</summary><p>{a}</p></details>
      ))}
    </div>
  );
}
