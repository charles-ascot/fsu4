const colours = {
  ok: 'bg-green-900/40 text-green-400',
  success: 'bg-green-900/40 text-green-400',
  processed: 'bg-green-900/40 text-green-400',
  error: 'bg-red-900/40 text-red-400',
  failed: 'bg-red-900/40 text-red-400',
  pending: 'bg-yellow-900/40 text-yellow-400',
  processing: 'bg-blue-900/40 text-blue-400',
}

export default function StatusBadge({ value }) {
  const cls = colours[value?.toLowerCase()] ?? 'bg-gray-800 text-gray-400'
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {value ?? '—'}
    </span>
  )
}
