export default function Badge({ tier }) {
  const t = (tier || 'LOW').toUpperCase()
  return (
    <span className={`badge ${t.toLowerCase()}`}>
      <span className="badge-dot" />
      {t}
    </span>
  )
}
