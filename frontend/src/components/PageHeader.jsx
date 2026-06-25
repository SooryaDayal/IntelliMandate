export default function PageHeader({ title, sub }) {
  return (
    <div className="mb-8 pb-6" style={{ borderBottom: '1px solid var(--border)' }}>
      <div
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: '1.75rem',
          fontWeight: 700,
          color: 'var(--text)',
          letterSpacing: '-0.03em',
          lineHeight: 1.2,
        }}
      >
        {title}
      </div>
      <div
        className="mt-1.5"
        style={{ fontSize: '0.82rem', color: 'var(--text3)', fontFamily: 'var(--font-mono)', letterSpacing: '0.03em' }}
      >
        {sub}
      </div>
    </div>
  )
}
