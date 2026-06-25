const accentMap = {
  accent: 'var(--accent)',
  critical: 'var(--critical)',
  high: 'var(--high)',
  low: 'var(--low)',
}

export default function MetricCard({ icon, value, label, sub, subColor, accent = 'accent', valueColor }) {
  return (
    <div
      className="relative overflow-hidden rounded-2xl p-5"
      style={{ background: 'var(--bg2)', border: '1px solid var(--border)' }}
    >
      <div
        className="absolute top-0 right-0 w-15 h-15 opacity-[0.05]"
        style={{
          background: accentMap[accent],
          width: 60,
          height: 60,
          borderRadius: '0 16px 0 60px',
        }}
      />
      {icon && <span className="block mb-3 text-lg">{icon}</span>}
      <div
        className="font-extrabold leading-none mb-1"
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: '2rem',
          letterSpacing: '-0.04em',
          color: valueColor || 'var(--text)',
        }}
      >
        {value}
      </div>
      <div
        className="uppercase"
        style={{
          fontSize: '0.7rem',
          color: 'var(--text3)',
          fontFamily: 'var(--font-mono)',
          letterSpacing: '0.08em',
        }}
      >
        {label}
      </div>
      {sub && (
        <div
          className="mt-2"
          style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: subColor || 'var(--text3)' }}
        >
          {sub}
        </div>
      )}
    </div>
  )
}
