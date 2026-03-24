import { NavLink } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const nav = [
  { to: '/dashboard', icon: '⚡', label: 'Dashboard' },
  { to: '/registry', icon: '🗂', label: 'Registry' },
  { to: '/agent', icon: '🤖', label: 'AI Agent' },
  { to: '/ingest', icon: '📥', label: 'Manual Ingest' },
  { to: '/sources', icon: '📡', label: 'Sources' },
  { to: '/config', icon: '⚙️', label: 'Config' },
]

export default function Sidebar() {
  const { user, logout } = useAuth()
  return (
    <aside className="w-56 flex-shrink-0 flex flex-col"
      style={{
        background: 'rgba(13, 17, 23, 0.7)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderRight: '1px solid rgba(255,255,255,0.08)',
      }}
    >
      <div className="px-5 py-5" style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
        <div className="col-header mb-0.5">Chimera Platform</div>
        <div className="gradient-text text-xl font-bold">FSU4</div>
        <div className="text-xs" style={{ color: 'var(--text-dim)' }}>Email Intelligence</div>
      </div>

      <nav className="flex-1 py-4 px-3 space-y-0.5">
        {nav.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'font-medium'
                  : 'hover:bg-white/5'
              }`
            }
            style={({ isActive }) => ({
              color: isActive ? 'var(--cyan)' : 'var(--text-dim)',
              background: isActive ? 'rgba(0,212,255,0.08)' : undefined,
            })}
          >
            <span className="text-base">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4" style={{ borderTop: '1px solid rgba(255,255,255,0.08)' }}>
        <div className="flex items-center gap-3 mb-3">
          {user?.picture && (
            <img src={user.picture} alt="" className="w-7 h-7 rounded-full" style={{ border: '1px solid rgba(0,212,255,0.3)' }} />
          )}
          <div className="min-w-0">
            <div className="text-sm truncate" style={{ color: 'var(--text)' }}>{user?.name}</div>
            <div className="text-xs truncate" style={{ color: 'var(--text-dim)' }}>{user?.email}</div>
          </div>
        </div>
        <button
          onClick={logout}
          className="w-full text-xs text-left transition-colors hover:opacity-80"
          style={{ color: 'var(--text-dim)' }}
        >
          Sign out
        </button>
      </div>
    </aside>
  )
}
