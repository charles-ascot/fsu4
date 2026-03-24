import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../api'
import LoadingSpinner from '../components/LoadingSpinner'
import StatusBadge from '../components/StatusBadge'

function Field({ label, value }) {
  if (!value) return null
  return (
    <div>
      <div className="col-header mb-1">{label}</div>
      <div className="text-sm" style={{ color: 'var(--text)' }}>{value}</div>
    </div>
  )
}

export default function RecordDetailPage() {
  const { id } = useParams()
  const [record, setRecord] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getRecord(id)
      .then(res => setRecord(res?.data))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="flex justify-center pt-20"><LoadingSpinner size={8} /></div>
  if (error) return <div className="text-red-400 text-sm p-6">{error}</div>
  if (!record) return null

  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/registry" className="text-sm transition-opacity hover:opacity-80" style={{ color: 'var(--text-dim)' }}>← Registry</Link>
        <span style={{ color: 'rgba(255,255,255,0.2)' }}>/</span>
        <span className="text-sm truncate" style={{ color: 'var(--text-dim)' }}>{record.title || record.subject}</span>
      </div>

      <div className="glass-panel p-6 mb-4">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <h1 className="text-xl font-bold" style={{ color: 'var(--text)' }}>{record.title || record.subject || 'Untitled'}</h1>
            {record.chimera_ref && (
              <span className="inline-block mt-1 px-2 py-0.5 bg-accent/20 text-accent text-xs font-mono rounded">
                {record.chimera_ref}
              </span>
            )}
          </div>
          <StatusBadge value={record.status} />
        </div>

        <div className="grid grid-cols-2 gap-5 mb-5">
          <Field label="Sender" value={record.from_address} />
          <Field label="Subject" value={record.subject} />
          <Field label="Intent" value={record.intent} />
          <Field label="Received" value={record.received_at ? new Date(record.received_at).toLocaleString('en-GB') : null} />
          <div>
            <div className="col-header mb-1">Relevancy</div>
            <div className="flex items-center gap-2">
              <div className="w-24 h-2 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.1)' }}>
                <div className="h-full rounded-full" style={{ width: `${(record.relevancy_score ?? 0) * 100}%`, background: 'var(--cyan)' }} />
              </div>
              <span className="text-sm" style={{ color: 'var(--text)' }}>{((record.relevancy_score ?? 0) * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>

        {record.summary && (
          <div className="mb-5">
            <div className="col-header mb-2">Summary</div>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-dim)' }}>{record.summary}</p>
          </div>
        )}

        {record.topics?.length > 0 && (
          <div className="mb-5">
            <div className="col-header mb-2">Topics</div>
            <div className="flex flex-wrap gap-1.5">
              {record.topics.map(t => (
                <span key={t} className="px-2 py-0.5 rounded text-xs"
                  style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', color: 'var(--text-dim)' }}>{t}</span>
              ))}
            </div>
          </div>
        )}

        {record.chimera_domain_tags?.length > 0 && (
          <div>
            <div className="col-header mb-2">Domain Tags</div>
            <div className="flex flex-wrap gap-1.5">
              {record.chimera_domain_tags.map(t => (
                <span key={t} className="px-2 py-0.5 rounded text-xs"
                  style={{ background: 'rgba(0,212,255,0.1)', border: '1px solid rgba(0,212,255,0.3)', color: 'var(--cyan)' }}>{t}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {record.gcs_path && (
        <div className="glass-panel p-5">
          <div className="col-header mb-1">GCS Path</div>
          <code className="text-xs font-mono" style={{ color: 'var(--text-dim)' }}>{record.gcs_path}</code>
        </div>
      )}
    </div>
  )
}
