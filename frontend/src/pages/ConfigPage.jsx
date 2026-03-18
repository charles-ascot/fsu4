import { useEffect, useState } from 'react'
import { api } from '../api'
import LoadingSpinner from '../components/LoadingSpinner'
import TagInput from '../components/TagInput'

export default function ConfigPage() {
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getConfig()
      .then(res => setConfig(res?.data ?? {}))
      .finally(() => setLoading(false))
  }, [])

  const update = (key, val) => setConfig(c => ({ ...c, [key]: val }))

  const save = async () => {
    setSaving(true); setError(null); setSaved(false)
    try {
      await api.updateConfig(config)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="flex justify-center pt-20"><LoadingSpinner size={8} /></div>

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-white mb-1">Configuration</h1>
      <p className="text-sm text-muted mb-6">Processing behaviour for incoming emails</p>

      <div className="bg-panel border border-border rounded-xl divide-y divide-border">

        <div className="p-5">
          <label className="block text-sm font-medium text-gray-300 mb-1">Ignore Senders</label>
          <p className="text-xs text-muted mb-2">Emails from these addresses are silently dropped</p>
          <TagInput
            value={config?.ignore_senders ?? []}
            onChange={v => update('ignore_senders', v)}
            placeholder="Enter email and press Enter…"
          />
        </div>

        <div className="p-5">
          <label className="block text-sm font-medium text-gray-300 mb-1">Ignore Subject Keywords</label>
          <p className="text-xs text-muted mb-2">Emails whose subject contains any of these are skipped</p>
          <TagInput
            value={config?.ignore_subjects_containing ?? []}
            onChange={v => update('ignore_subjects_containing', v)}
            placeholder="Enter keyword and press Enter…"
          />
        </div>

        <div className="p-5">
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Minimum Relevancy Threshold — <span className="text-accent">{((config?.min_relevancy_threshold ?? 0) * 100).toFixed(0)}%</span>
          </label>
          <p className="text-xs text-muted mb-3">Records below this score are still stored but flagged as low relevance</p>
          <input
            type="range" min={0} max={1} step={0.05}
            value={config?.min_relevancy_threshold ?? 0}
            onChange={e => update('min_relevancy_threshold', parseFloat(e.target.value))}
            className="w-full accent-accent"
          />
          <div className="flex justify-between text-xs text-muted mt-1"><span>0%</span><span>100%</span></div>
        </div>

        <div className="p-5">
          <label className="block text-sm font-medium text-gray-300 mb-1">Max Attachment Size (MB)</label>
          <input
            type="number" min={1} max={100}
            value={config?.max_attachment_size_mb ?? 50}
            onChange={e => update('max_attachment_size_mb', parseInt(e.target.value))}
            className="w-32 bg-surface border border-border rounded-lg px-3 py-2 text-sm text-gray-200 outline-none focus:border-accent"
          />
        </div>

        <div className="p-5">
          <label className="block text-sm font-medium text-gray-300 mb-3">Processing Features</label>
          <div className="space-y-3">
            {[
              ['enable_ocr', 'Image OCR (Vision API)'],
              ['enable_transcription', 'Audio Transcription (Speech-to-Text)'],
              ['enable_pdf_extraction', 'PDF Text Extraction'],
              ['enable_docx_extraction', 'Word Document Extraction'],
            ].map(([key, label]) => (
              <label key={key} className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={config?.[key] ?? true}
                  onChange={e => update(key, e.target.checked)}
                  className="w-4 h-4 accent-accent rounded"
                />
                <span className="text-sm text-gray-300">{label}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="p-5 flex items-center gap-4">
          <button onClick={save} disabled={saving}
            className="px-5 py-2 bg-accent hover:bg-accent-dim text-white text-sm rounded-lg transition-colors disabled:opacity-60">
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
          {saved && <span className="text-sm text-green-400">✓ Saved</span>}
          {error && <span className="text-sm text-red-400">{error}</span>}
        </div>
      </div>
    </div>
  )
}
