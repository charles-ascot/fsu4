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
    <aside className="w-56 flex-shrink-0 bg-panel border-r border-border flex flex-col">
      <div className="px-5 py-5 border-b border-border">
        <div className="text-xs font-semibold tracking-widest text-muted uppercase mb-0.5">Chimera</div>
        <div className="text-lg font-bold text-white">FSU4</div>
        <div className="text-xs text-muted">Email Intelligence</div>
      </div>

      <nav className="flex-1 py-4 px-3 space-y-0.5">
        {nav.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-accent/15 text-accent font-medium'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
              }`
            }
          >
            <span className="text-base">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-border">
        <div className="flex items-center gap-3 mb-3">
          {user?.picture && (
            <img src={user.picture} alt="" className="w-7 h-7 rounded-full" />
          )}
          <div className="min-w-0">
            <div className="text-sm text-gray-200 truncate">{user?.name}</div>
            <div className="text-xs text-muted truncate">{user?.email}</div>
          </div>
        </div>
        <button
          onClick={logout}
          className="w-full text-xs text-muted hover:text-gray-300 text-left transition-colors"
        >
          Sign out
        </button>
      </div>
    </aside>
  )
}
