export default function ErrorBanner({ message }) {
  if (!message) return null
  return (
    <div
      className="rounded-xl px-5 py-3.5 mb-4"
      style={{
        background: 'rgba(244,63,94,0.08)',
        border: '1px solid rgba(244,63,94,0.2)',
        fontFamily: 'var(--font-mono)',
        fontSize: '0.78rem',
        color: 'var(--critical)',
      }}
    >
      ⚠ Backend unreachable — {message}
    </div>
  )
}
