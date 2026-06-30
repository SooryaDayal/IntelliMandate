import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'

export default function Layout() {
  return (
    <div className="flex min-h-screen" style={{ background: 'var(--bg)' }}>
      <Sidebar />
      <main className="flex-1 px-10 py-8" style={{ maxWidth: 1400 }}>
        <Outlet />
      </main>
    </div>
  )
}
