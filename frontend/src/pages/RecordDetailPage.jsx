import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../api'
import LoadingSpinner from '../components/LoadingSpinner'
import StatusBadge from '../components/StatusBadge'

function Field({ label, value }) {
  if (!value) return null
  return (
    <div>
      <div className="text-xs text-muted uppercase tracking-wide mb-1">{label}</div>
      <div className="text-sm text-gray-200">{value}</div>
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
        <Link to="/registry" className="text-muted hover:text-gray-300 text-sm">← Registry</Link>
        <span className="text-border">/</span>
        <span className="text-sm text-gray-400 truncate">{record.title || record.subject}</span>
      </div>

      <div className="bg-panel border border-border rounded-xl p-6 mb-4">
        <div className="flex items-start justify-between gap-4 mb-5">
          <h1 className="text-xl font-bold text-white">{record.title || record.subject || 'Untitled'}</h1>
          <StatusBadge value={record.status} />
        </div>

        <div className="grid grid-cols-2 gap-5 mb-5">
          <Field label="Sender" value={record.from_address} />
          <Field label="Subject" value={record.subject} />
          <Field label="Intent" value={record.intent} />
          <Field label="Received" value={record.received_at ? new Date(record.received_at).toLocaleString('en-GB') : null} />
          <div>
            <div className="text-xs text-muted uppercase tracking-wide mb-1">Relevancy</div>
            <div className="flex items-center gap-2">
              <div className="w-24 h-2 bg-border rounded-full overflow-hidden">
                <div className="h-full bg-accent rounded-full" style={{ width: `${(record.relevancy_score ?? 0) * 100}%` }} />
              </div>
              <span className="text-sm text-gray-200">{((record.relevancy_score ?? 0) * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>

        {record.summary && (
          <div className="mb-5">
            <div className="text-xs text-muted uppercase tracking-wide mb-2">Summary</div>
            <p className="text-sm text-gray-300 leading-relaxed">{record.summary}</p>
          </div>
        )}

        {record.topics?.length > 0 && (
          <div className="mb-5">
            <div className="text-xs text-muted uppercase tracking-wide mb-2">Topics</div>
            <div className="flex flex-wrap gap-1.5">
              {record.topics.map(t => (
                <span key={t} className="px-2 py-0.5 bg-surface border border-border text-xs text-gray-300 rounded">{t}</span>
              ))}
            </div>
          </div>
        )}

        {record.chimera_domain_tags?.length > 0 && (
          <div>
            <div className="text-xs text-muted uppercase tracking-wide mb-2">Domain Tags</div>
            <div className="flex flex-wrap gap-1.5">
              {record.chimera_domain_tags.map(t => (
                <span key={t} className="px-2 py-0.5 bg-accent/15 text-accent text-xs rounded">{t}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {record.gcs_path && (
        <div className="bg-panel border border-border rounded-xl p-5">
          <div className="text-xs text-muted uppercase tracking-wide mb-1">GCS Path</div>
          <code className="text-xs text-gray-400 font-mono">{record.gcs_path}</code>
        </div>
      )}
    </div>
  )
}
