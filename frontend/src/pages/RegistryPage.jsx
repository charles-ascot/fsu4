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
          <h1 className="text-2xl font-bold text-white">Registry</h1>
          <p className="text-sm text-muted mt-0.5">{total} total records</p>
        </div>
      </div>

      <div className="flex gap-3 mb-4">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search title, sender, subject..."
          className="flex-1 bg-panel border border-border rounded-lg px-4 py-2 text-sm text-gray-200 placeholder-muted outline-none focus:border-accent transition-colors"
        />
        <select
          value={intent}
          onChange={e => { setIntent(e.target.value); load(0, e.target.value) }}
          className="bg-panel border border-border rounded-lg px-3 py-2 text-sm text-gray-200 outline-none focus:border-accent"
        >
          {INTENTS.map(i => <option key={i} value={i}>{i || 'All intents'}</option>)}
        </select>
        <button onClick={() => load(0)} className="px-4 py-2 bg-accent hover:bg-accent-dim text-white text-sm rounded-lg transition-colors">
          Refresh
        </button>
      </div>

      <div className="bg-panel border border-border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-xs text-muted uppercase tracking-wide">
              <th className="text-left px-5 py-3">Title / Subject</th>
              <th className="text-left px-4 py-3">Sender</th>
              <th className="text-left px-4 py-3">Intent</th>
              <th className="text-left px-4 py-3">Relevancy</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Date</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading ? (
              <tr><td colSpan={6} className="py-12 text-center"><LoadingSpinner /></td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={6} className="py-12 text-center text-muted">No records found</td></tr>
            ) : filtered.map(rec => (
              <tr key={rec.record_id} className="hover:bg-white/5 transition-colors">
                <td className="px-5 py-3">
                  <Link to={`/registry/${rec.record_id}`} className="text-gray-200 hover:text-accent transition-colors">
                    <div className="font-medium truncate max-w-xs">{rec.title || rec.subject || 'Untitled'}</div>
                    {rec.summary && <div className="text-xs text-muted truncate max-w-xs">{rec.summary}</div>}
                  </Link>
                </td>
                <td className="px-4 py-3 text-muted text-xs truncate max-w-[160px]">{rec.from_address}</td>
                <td className="px-4 py-3"><StatusBadge value={rec.intent} /></td>
                <td className="px-4 py-3 text-gray-300">
                  {rec.relevancy_score != null ? (
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-border rounded-full overflow-hidden">
                        <div className="h-full bg-accent rounded-full" style={{ width: `${rec.relevancy_score * 100}%` }} />
                      </div>
                      <span className="text-xs text-muted">{(rec.relevancy_score * 100).toFixed(0)}%</span>
                    </div>
                  ) : '—'}
                </td>
                <td className="px-4 py-3"><StatusBadge value={rec.status} /></td>
                <td className="px-4 py-3 text-xs text-muted whitespace-nowrap">
                  {rec.received_at ? new Date(rec.received_at).toLocaleDateString('en-GB') : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-border">
            <span className="text-xs text-muted">Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}</span>
            <div className="flex gap-2">
              <button disabled={offset === 0} onClick={() => load(offset - PAGE_SIZE)}
                className="px-3 py-1 text-xs bg-surface border border-border rounded disabled:opacity-40 hover:border-accent transition-colors">
                Previous
              </button>
              <button disabled={offset + PAGE_SIZE >= total} onClick={() => load(offset + PAGE_SIZE)}
                className="px-3 py-1 text-xs bg-surface border border-border rounded disabled:opacity-40 hover:border-accent transition-colors">
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
