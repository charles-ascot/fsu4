import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import LoadingSpinner from '../components/LoadingSpinner'
import StatusBadge from '../components/StatusBadge'

function StatCard({ label, value, sub }) {
  return (
    <div className="bg-panel border border-border rounded-xl p-5">
      <div className="text-xs text-muted uppercase tracking-wide mb-1">{label}</div>
      <div className="text-3xl font-bold text-white">{value ?? '—'}</div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
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
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-muted mt-0.5">FSU4 Email Intelligence — {new Date().toLocaleDateString('en-GB', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-panel border border-border rounded-lg">
          <div className={`w-2 h-2 rounded-full ${health?.status === 'ok' ? 'bg-green-400' : 'bg-red-400'}`} />
          <span className="text-sm text-gray-300">{health?.status === 'ok' ? 'Service healthy' : 'Service error'}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Records" value={stats.total_records ?? 0} />
        <StatCard label="Firestore" value={status?.firestore === 'ok' ? '✓ OK' : '✗ Error'} />
        <StatCard label="Processed" value={stats.by_status?.processed ?? 0} sub="emails ingested" />
        <StatCard label="Pending" value={stats.by_status?.pending ?? 0} sub="in queue" />
      </div>

      {Object.keys(stats.by_intent ?? {}).length > 0 && (
        <div className="bg-panel border border-border rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold text-gray-300 mb-3">Records by Intent</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(stats.by_intent).map(([intent, count]) => (
              <div key={intent} className="flex items-center gap-2 px-3 py-1.5 bg-surface rounded-lg border border-border">
                <span className="text-sm text-gray-200">{intent}</span>
                <span className="text-xs text-muted">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-panel border border-border rounded-xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-gray-300">Recent Records</h2>
          <Link to="/registry" className="text-xs text-accent hover:underline">View all</Link>
        </div>
        {recent.length === 0 ? (
          <div className="px-5 py-10 text-center text-muted text-sm">No records yet</div>
        ) : (
          <div className="divide-y divide-border">
            {recent.map(rec => (
              <Link key={rec.id} to={`/registry/${rec.id}`} className="flex items-center gap-4 px-5 py-3 hover:bg-white/5 transition-colors">
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-200 truncate">{rec.title || rec.subject || 'Untitled'}</div>
                  <div className="text-xs text-muted truncate">{rec.sender}</div>
                </div>
                <StatusBadge value={rec.status} />
                <div className="text-xs text-muted whitespace-nowrap">
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
