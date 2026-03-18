import { useState } from 'react'
import { api } from '../api'

export default function ManualIngestPage() {
  const [messageId, setMessageId] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!messageId.trim()) return
    setLoading(true); setResult(null); setError(null)
    try {
      const res = await api.manualIngest(messageId.trim())
      setResult(res)
      setMessageId('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-bold text-white mb-1">Manual Ingest</h1>
      <p className="text-sm text-muted mb-6">Process a specific Gmail message by ID</p>

      <div className="bg-panel border border-border rounded-xl p-5 mb-4">
        <p className="text-xs text-muted mb-4">
          Find the message ID in Gmail: open the email → More options (⋮) → Show original — the Message ID is at the top, or use the URL hash after <code className="text-gray-400">#inbox/</code>.
        </p>
        <form onSubmit={submit} className="flex gap-3">
          <input
            value={messageId}
            onChange={e => setMessageId(e.target.value)}
            placeholder="Gmail message ID"
            className="flex-1 bg-surface border border-border rounded-lg px-4 py-2 text-sm text-gray-200 placeholder-muted outline-none focus:border-accent transition-colors font-mono"
          />
          <button type="submit" disabled={!messageId.trim() || loading}
            className="px-4 py-2 bg-accent hover:bg-accent-dim text-white text-sm rounded-lg transition-colors disabled:opacity-60">
            {loading ? 'Processing…' : 'Ingest'}
          </button>
        </form>
      </div>

      {result && (
        <div className="bg-green-900/20 border border-green-800/40 rounded-xl p-5">
          <div className="text-sm font-medium text-green-400 mb-2">✓ Ingest successful</div>
          <pre className="text-xs text-gray-400 overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(result?.data, null, 2)}
          </pre>
        </div>
      )}

      {error && (
        <div className="bg-red-900/20 border border-red-800/40 rounded-xl p-5">
          <div className="text-sm font-medium text-red-400 mb-1">Ingest failed</div>
          <div className="text-xs text-gray-400">{error}</div>
        </div>
      )}
    </div>
  )
}
