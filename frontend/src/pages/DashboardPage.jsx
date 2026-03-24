import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import LoadingSpinner from '../components/LoadingSpinner'
import StatusBadge from '../components/StatusBadge'

function StatCard({ label, value, sub }) {
  return (
    <div className="glass-panel p-5">
      <div className="col-header mb-1">{label}</div>
      <div className="text-3xl font-bold" style={{ color: 'var(--text)' }}>{value ?? '—'}</div>
      {sub && <div className="text-xs mt-1" style={{ color: 'var(--text-dim)' }}>{sub}</div>}
    </div>
  )
}

export default function DashboardPage() {
  const [status, setStatus] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [recent, setRecent] = useState([])
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      api.health(),
      api.status(),
      api.getMetrics(),
      api.getRegistry({ limit: 5 }),
    ]).then(([h, s, m, r]) => {
      if (h.status === 'fulfilled') setHealth(h.value)
      if (s.status === 'fulfilled') setStatus(s.value?.data)
      if (m.status === 'fulfilled') setMetrics(m.value?.data)
      if (r.status === 'fulfilled') setRecent(r.value?.data?.records ?? [])
      setLoading(false)
    })
  }, [])

  if (loading) return <div className="flex justify-center pt-20"><LoadingSpinner size={8} /></div>

  const stats = status?.registry_stats ?? {}

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="gradient-text text-2xl font-bold">Dashboard</h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>FSU4 Email Intelligence · {new Date().toLocaleDateString('en-GB', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
          style={{ background: 'rgba(20,25,45,0.6)', border: '1px solid rgba(255,255,255,0.1)' }}>
          <div className={`w-2 h-2 rounded-full ${health?.status === 'ok' ? 'bg-green-400' : 'bg-red-400'}`} />
          <span className="text-sm" style={{ color: 'var(--text)' }}>{health?.status === 'ok' ? 'Service healthy' : 'Service error'}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Records" value={stats.total_records ?? 0} />
        <StatCard label="Firestore" value={status?.firestore === 'ok' ? '✓ OK' : '✗ Error'} />
        <StatCard label="Processed" value={stats.by_status?.processed ?? 0} sub="emails ingested" />
        <StatCard label="Pending" value={stats.by_status?.pending ?? 0} sub="in queue" />
      </div>

      {Object.keys(stats.by_intent ?? {}).length > 0 && (
        <div className="glass-panel p-5 mb-6">
          <div className="col-header mb-3">Records by Intent</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(stats.by_intent).map(([intent, count]) => (
              <div key={intent} className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
                style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.08)' }}>
                <span className="text-sm" style={{ color: 'var(--text)' }}>{intent}</span>
                <span className="text-xs" style={{ color: 'var(--text-dim)' }}>{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="glass-panel overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
          <div className="col-header">Recent Records</div>
          <Link to="/registry" className="text-xs transition-opacity hover:opacity-80" style={{ color: 'var(--cyan)' }}>View all</Link>
        </div>
        {recent.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm" style={{ color: 'var(--text-dim)' }}>No records yet</div>
        ) : (
          <div>
            {recent.map(rec => (
              <Link key={rec.record_id} to={`/registry/${rec.record_id}`}
                className="flex items-center gap-4 px-5 py-3 transition-colors hover:bg-white/5"
                style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <div className="flex-1 min-w-0">
                  <div className="text-sm truncate" style={{ color: 'var(--text)' }}>{rec.title || rec.subject || 'Untitled'}</div>
                  <div className="text-xs truncate" style={{ color: 'var(--text-dim)' }}>{rec.from_address}</div>
                </div>
                <StatusBadge value={rec.status} />
                <div className="text-xs whitespace-nowrap" style={{ color: 'var(--text-dim)' }}>
                  {rec.received_at ? new Date(rec.received_at).toLocaleDateString('en-GB') : ''}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
