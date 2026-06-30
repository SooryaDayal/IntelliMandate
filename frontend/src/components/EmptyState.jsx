export default function EmptyState({ icon = '▦', text = 'No data', sub = '' }) {
  return (
    <div className="text-center py-16 px-8" style={{ color: 'var(--text3)' }}>
      <span className="block mb-4 text-3xl">{icon}</span>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: '1rem', color: 'var(--text2)' }}>
        {text}
      </div>
      {sub && (
        <div className="mt-2" style={{ fontSize: '0.78rem', fontFamily: 'var(--font-mono)' }}>
          {sub}
        </div>
      )}
    </div>
  )
}
