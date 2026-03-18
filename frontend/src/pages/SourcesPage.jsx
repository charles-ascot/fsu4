import { useEffect, useState } from 'react'
import { api } from '../api'
import LoadingSpinner from '../components/LoadingSpinner'

export default function SourcesPage() {
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ email_address: '', display_name: '', description: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    api.getSources()
      .then(res => setSources(res?.data ?? []))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const submit = async (e) => {
    e.preventDefault()
    if (!form.email_address) return
    setSaving(true); setError(null)
    try {
      await api.createSource(form)
      setForm({ email_address: '', display_name: '', description: '' })
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    if (!confirm('Remove this source?')) return
    await api.deleteSource(id)
    load()
  }

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-white mb-1">Sources</h1>
      <p className="text-sm text-muted mb-6">Email addresses that forward to chimera.data.in@gmail.com</p>

      <div className="bg-panel border border-border rounded-xl p-5 mb-6">
        <h2 className="text-sm font-semibold text-gray-300 mb-4">Register New Source</h2>
        <form onSubmit={submit} className="space-y-3">
          <input
            required
            type="email"
            placeholder="source@example.com"
            value={form.email_address}
            onChange={e => setForm(f => ({ ...f, email_address: e.target.value }))}
            className="w-full bg-surface border border-border rounded-lg px-4 py-2 text-sm text-gray-200 placeholder-muted outline-none focus:border-accent transition-colors"
          />
          <input
            placeholder="Display name"
            value={form.display_name}
            onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
            className="w-full bg-surface border border-border rounded-lg px-4 py-2 text-sm text-gray-200 placeholder-muted outline-none focus:border-accent transition-colors"
          />
          <textarea
            placeholder="Description (what does this source send?)"
            rows={2}
            value={form.description}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            className="w-full bg-surface border border-border rounded-lg px-4 py-2 text-sm text-gray-200 placeholder-muted outline-none focus:border-accent transition-colors resize-none"
          />
          {error && <p className="text-xs text-red-400">{error}</p>}
          <button type="submit" disabled={saving}
            className="px-4 py-2 bg-accent hover:bg-accent-dim text-white text-sm rounded-lg transition-colors disabled:opacity-60">
            {saving ? 'Adding…' : 'Add Source'}
          </button>
        </form>
      </div>

      <div className="bg-panel border border-border rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border text-sm font-semibold text-gray-300">
          Registered Sources ({sources.length})
        </div>
        {loading ? (
          <div className="py-12 flex justify-center"><LoadingSpinner /></div>
        ) : sources.length === 0 ? (
          <div className="py-12 text-center text-muted text-sm">No sources registered</div>
        ) : (
          <div className="divide-y divide-border">
            {sources.map(src => (
              <div key={src.id} className="flex items-start justify-between gap-4 px-5 py-4">
                <div>
                  <div className="text-sm font-medium text-gray-200">{src.display_name || src.email_address}</div>
                  <div className="text-xs text-muted">{src.email_address}</div>
                  {src.description && <div className="text-xs text-gray-400 mt-1">{src.description}</div>}
                </div>
                <button onClick={() => remove(src.id)}
                  className="text-xs text-muted hover:text-red-400 transition-colors flex-shrink-0">
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
