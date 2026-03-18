import { useState } from 'react'

export default function TagInput({ value = [], onChange, placeholder }) {
  const [input, setInput] = useState('')

  const add = (tag) => {
    const t = tag.trim()
    if (t && !value.includes(t)) onChange([...value, t])
    setInput('')
  }

  const remove = (tag) => onChange(value.filter(v => v !== tag))

  const onKey = (e) => {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(input) }
    if (e.key === 'Backspace' && !input) remove(value[value.length - 1])
  }

  return (
    <div className="flex flex-wrap gap-1.5 min-h-[42px] p-2 bg-surface border border-border rounded-lg focus-within:border-accent transition-colors">
      {value.map(tag => (
        <span key={tag} className="flex items-center gap-1 px-2 py-0.5 bg-accent/20 text-accent text-sm rounded">
          {tag}
          <button type="button" onClick={() => remove(tag)} className="text-accent/60 hover:text-accent">×</button>
        </span>
      ))}
      <input
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={onKey}
        onBlur={() => input && add(input)}
        placeholder={value.length === 0 ? placeholder : ''}
        className="flex-1 min-w-[120px] bg-transparent outline-none text-sm text-gray-200 placeholder-muted"
      />
    </div>
  )
}
