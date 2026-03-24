const styles = {
  ok:         { background: 'rgba(74,222,128,0.1)',  border: '1px solid rgba(74,222,128,0.3)',  color: 'var(--green)' },
  success:    { background: 'rgba(74,222,128,0.1)',  border: '1px solid rgba(74,222,128,0.3)',  color: 'var(--green)' },
  processed:  { background: 'rgba(74,222,128,0.1)',  border: '1px solid rgba(74,222,128,0.3)',  color: 'var(--green)' },
  error:      { background: 'rgba(255,107,107,0.1)', border: '1px solid rgba(255,107,107,0.3)', color: 'var(--red)' },
  failed:     { background: 'rgba(255,107,107,0.1)', border: '1px solid rgba(255,107,107,0.3)', color: 'var(--red)' },
  pending:    { background: 'rgba(251,191,36,0.1)',  border: '1px solid rgba(251,191,36,0.3)',  color: '#FBBF24' },
  processing: { background: 'rgba(0,212,255,0.1)',   border: '1px solid rgba(0,212,255,0.3)',   color: 'var(--cyan)' },
}

const defaultStyle = { background: 'rgba(136,136,136,0.1)', border: '1px solid rgba(136,136,136,0.2)', color: 'var(--text-dim)' }

export default function StatusBadge({ value }) {
  const s = styles[value?.toLowerCase()] ?? defaultStyle
  return (
    <span className="inline-block px-2 py-0.5 rounded text-xs font-medium" style={s}>
      {value ?? '—'}
    </span>
  )
}
