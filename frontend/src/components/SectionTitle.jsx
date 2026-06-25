export default function SectionTitle({ children, suffix }) {
  return (
    <div
      className="flex items-center gap-2 mb-3 mt-6"
      style={{ fontFamily: 'var(--font-display)', fontSize: '1rem', fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.01em' }}
    >
      {children}
      {suffix && (
        <span style={{ fontSize: '0.75rem', color: 'var(--text3)', fontFamily: 'var(--font-mono)', fontWeight: 400 }}>
          {suffix}
        </span>
      )}
      <span className="flex-1 h-px" style={{ background: 'var(--border)', marginLeft: '0.5rem' }} />
    </div>
  )
}
