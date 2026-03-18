import { useState } from 'react'
import { api } from '../api'
import LoadingSpinner from '../components/LoadingSpinner'

export default function AgentPage() {
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)

  const send = async () => {
    const q = query.trim()
    if (!q || loading) return
    setMessages(m => [...m, { role: 'user', text: q }])
    setQuery('')
    setLoading(true)
    try {
      const res = await api.agentQuery(q)
      const answer = res?.data?.response ?? res?.data?.answer ?? JSON.stringify(res?.data, null, 2)
      setMessages(m => [...m, { role: 'agent', text: answer }])
    } catch (e) {
      setMessages(m => [...m, { role: 'error', text: e.message }])
    } finally {
      setLoading(false)
    }
  }

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <div className="max-w-3xl flex flex-col h-[calc(100vh-6rem)]">
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-white">AI Agent</h1>
        <p className="text-sm text-muted mt-0.5">Query your intelligence registry in natural language</p>
      </div>

      <div className="flex-1 bg-panel border border-border rounded-xl flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-muted text-sm pt-10">
              <div className="text-3xl mb-3">🤖</div>
              <p>Ask anything about your email intelligence data.</p>
              <div className="mt-4 space-y-2 text-xs">
                {[
                  'What were the most important emails this week?',
                  'Show me all alerts from the last 7 days',
                  'Summarise the market data signals',
                ].map(s => (
                  <button key={s} onClick={() => setQuery(s)}
                    className="block mx-auto px-3 py-1.5 bg-surface border border-border rounded-lg hover:border-accent transition-colors">
                    "{s}"
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] px-4 py-3 rounded-xl text-sm whitespace-pre-wrap leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-accent/20 text-gray-200 rounded-br-sm'
                  : msg.role === 'error'
                  ? 'bg-red-900/30 text-red-400 rounded-bl-sm'
                  : 'bg-surface border border-border text-gray-300 rounded-bl-sm'
              }`}>
                {msg.role === 'agent' && (
                  <div className="text-xs text-accent font-medium mb-1">FSU4 Agent</div>
                )}
                {msg.text}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-surface border border-border px-4 py-3 rounded-xl rounded-bl-sm">
                <LoadingSpinner size={4} />
              </div>
            </div>
          )}
        </div>

        <div className="border-t border-border p-4 flex gap-3">
          <textarea
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={onKey}
            placeholder="Ask the agent… (Enter to send)"
            rows={2}
            className="flex-1 bg-surface border border-border rounded-lg px-4 py-2 text-sm text-gray-200 placeholder-muted outline-none focus:border-accent transition-colors resize-none"
          />
          <button onClick={send} disabled={!query.trim() || loading}
            className="px-4 py-2 bg-accent hover:bg-accent-dim text-white text-sm rounded-lg transition-colors disabled:opacity-40 self-end">
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
