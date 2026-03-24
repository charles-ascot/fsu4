import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import LoadingSpinner from '../components/LoadingSpinner'
import StatusBadge from '../components/StatusBadge'

const INTENTS = ['', 'informational', 'actionable', 'alert', 'report', 'operational']
const PAGE_SIZE = 20

export default function RegistryPage() {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [intent, setIntent] = useState('')
  const [search, setSearch] = useState('')

  const load = (off = 0, intentFilter = intent) => {
    setLoading(true)
    const params = { limit: PAGE_SIZE, offset: off }
    if (intentFilter) params.intent = intentFilter
    api.getRegistry(params)
      .then(res => {
        setRecords(res?.data?.records ?? [])
        setTotal(res?.data?.count ?? 0)
        setOffset(off)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load(0) }, [])

  const filtered = search
    ? records.filter(r =>
        (r.title ?? '').toLowerCase().includes(search.toLowerCase()) ||
        (r.sender ?? '').toLowerCase().includes(search.toLowerCase()) ||
        (r.subject ?? '').toLowerCase().includes(search.toLowerCase())
      )
    : records

  return (
    <div className="max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="gradient-text text-2xl font-bold">Registry</h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>{total} total records</p>
        </div>
      </div>

      <div className="flex gap-3 mb-4">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search title, sender, subject..."
          className="flex-1 rounded-lg px-4 py-2 text-sm outline-none transition-colors"
          style={{ background: 'rgba(20,25,45,0.6)', border: '1px solid rgba(255,255,255,0.1)', color: 'var(--text)' }}
          onFocus={e => e.target.style.borderColor = 'rgba(0,212,255,0.5)'}
          onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
        />
        <select
          value={intent}
          onChange={e => { setIntent(e.target.value); load(0, e.target.value) }}
          className="rounded-lg px-3 py-2 text-sm outline-none"
          style={{ background: 'rgba(20,25,45,0.6)', border: '1px solid rgba(255,255,255,0.1)', color: 'var(--text)' }}
        >
          {INTENTS.map(i => <option key={i} value={i}>{i || 'All intents'}</option>)}
        </select>
        <button onClick={() => load(0)}
          className="px-4 py-2 text-sm rounded-lg font-medium transition-all hover:opacity-90"
          style={{ background: 'rgba(0,212,255,0.12)', border: '1px solid rgba(0,212,255,0.3)', color: 'var(--cyan)' }}>
          Refresh
        </button>
      </div>

      <div className="glass-panel overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
              <th className="col-header text-left px-5 py-3">Title / Subject</th>
              <th className="col-header text-left px-4 py-3">Sender</th>
              <th className="col-header text-left px-4 py-3">Intent</th>
              <th className="col-header text-left px-4 py-3">Relevancy</th>
              <th className="col-header text-left px-4 py-3">Status</th>
              <th className="col-header text-left px-4 py-3">Date</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="py-12 text-center"><LoadingSpinner /></td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={6} className="py-12 text-center text-muted">No records found</td></tr>
            ) : filtered.map(rec => (
              <tr key={rec.record_id} className="hover:bg-white/5 transition-colors" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <td className="px-5 py-3">
                  <Link to={`/registry/${rec.record_id}`} className="transition-opacity hover:opacity-80" style={{ color: 'var(--text)' }}>
                    <div className="font-medium truncate max-w-xs">{rec.title || rec.subject || 'Untitled'}</div>
                    {rec.chimera_ref && (
                      <span className="inline-block mt-0.5 px-1.5 py-0.5 bg-accent/20 text-accent text-[10px] font-mono rounded">
                        {rec.chimera_ref}
                      </span>
                    )}
                    {rec.summary && <div className="text-xs text-muted truncate max-w-xs">{rec.summary}</div>}
                  </Link>
                </td>
                <td className="px-4 py-3 text-xs truncate max-w-[160px]" style={{ color: 'var(--text-dim)' }}>{rec.from_address}</td>
                <td className="px-4 py-3"><StatusBadge value={rec.intent} /></td>
                <td className="px-4 py-3" style={{ color: 'var(--text)' }}>
                  {rec.relevancy_score != null ? (
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.1)' }}>
                        <div className="h-full rounded-full" style={{ width: `${rec.relevancy_score * 100}%`, background: 'var(--cyan)' }} />
                      </div>
                      <span className="text-xs" style={{ color: 'var(--text-dim)' }}>{(rec.relevancy_score * 100).toFixed(0)}%</span>
                    </div>
                  ) : '—'}
                </td>
                <td className="px-4 py-3"><StatusBadge value={rec.status} /></td>
                <td className="px-4 py-3 text-xs whitespace-nowrap" style={{ color: 'var(--text-dim)' }}>
                  {rec.received_at ? new Date(rec.received_at).toLocaleDateString('en-GB') : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-5 py-3" style={{ borderTop: '1px solid rgba(255,255,255,0.08)' }}>
            <span className="text-xs" style={{ color: 'var(--text-dim)' }}>Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}</span>
            <div className="flex gap-2">
              <button disabled={offset === 0} onClick={() => load(offset - PAGE_SIZE)}
                className="px-3 py-1 text-xs rounded disabled:opacity-40 transition-colors"
                style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', color: 'var(--text-dim)' }}>
                Previous
              </button>
              <button disabled={offset + PAGE_SIZE >= total} onClick={() => load(offset + PAGE_SIZE)}
                className="px-3 py-1 text-xs rounded disabled:opacity-40 transition-colors"
                style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', color: 'var(--text-dim)' }}>
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
