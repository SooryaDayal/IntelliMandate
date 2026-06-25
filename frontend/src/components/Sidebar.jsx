import { NavLink } from 'react-router-dom'
import { LayoutDashboard, FileStack, ScanSearch, UploadCloud, ShieldCheck, FileUp } from 'lucide-react'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/mandates', label: 'Mandates', icon: FileStack },
  { to: '/map/latest', label: 'MAP Detail', icon: ScanSearch, matchPrefix: '/map' },
  { to: '/upload-circular', label: 'Upload Circular', icon: FileUp },
  { to: '/evidence', label: 'Evidence Upload', icon: UploadCloud },
  { to: '/audit-trail', label: 'Audit Trail', icon: ShieldCheck },
]

export default function Sidebar() {
  return (
    <aside
      className="w-65 flex flex-col shrink-0"
      style={{ width: 260, background: 'var(--bg2)', borderRight: '1px solid var(--border)', minHeight: '100vh' }}
    >
      <div className="px-6 pt-7 pb-4" style={{ borderBottom: '1px solid var(--border)' }}>
        <div
          className="flex items-center gap-2"
          style={{ fontFamily: "'Poppins', sans-serif", fontSize: '1.25rem', fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.02em' }}
        >
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)', flexShrink: 0 }} />
          IntelliMandate
        </div>
        <div
          className="mt-1 pl-5"
          style={{ fontSize: '0.7rem', color: 'var(--text3)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase' }}
        >
        </div>
      </div>

      <nav className="px-3 py-2 flex-1">
        {navItems.map(({ to, label, icon: Icon, end, matchPrefix }) => (
          <NavLink
            key={label}
            to={to}
            end={end}
            className={({ isActive }) => {
              const active = matchPrefix
                ? window.location.pathname.startsWith(matchPrefix)
                : isActive
              return [
                'flex items-center gap-3 px-3 py-2.5 rounded-lg mb-0.5 text-sm transition-colors',
                active ? 'font-medium' : '',
              ].join(' ')
            }}
            style={({ isActive }) => {
              const active = matchPrefix ? window.location.pathname.startsWith(matchPrefix) : isActive
              return active
                ? { background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.2)', color: 'var(--accent)' }
                : { color: 'var(--text2)', border: '1px solid transparent' }
            }}
          >
            <Icon size={16} strokeWidth={2} style={{ flexShrink: 0 }} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-6 py-4" style={{ borderTop: '1px solid var(--border)', background: 'var(--bg2)' }}>
        <p style={{ fontSize: '0.7rem', color: 'var(--text3)', fontFamily: 'var(--font-mono)' }}>
          <span
            className="inline-block mr-1.5"
            style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--medium)', verticalAlign: 'middle' }}
          />
          IntelliMandate v1.0
        </p>
      </div>
    </aside>
  )
}
