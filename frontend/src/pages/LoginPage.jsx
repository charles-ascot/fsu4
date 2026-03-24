import { GoogleLogin } from '@react-oauth/google'
import { useAuth } from '../contexts/AuthContext'
import { useState } from 'react'

export default function LoginPage() {
  const { login } = useAuth()
  const [error, setError] = useState(null)

  const handleSuccess = (res) => {
    try {
      login(res)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center" style={{ background: '#0d1117' }}>
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(circle at 30% 30%, rgba(157,78,221,0.15) 0%, transparent 50%), radial-gradient(circle at 75% 75%, rgba(0,212,255,0.08) 0%, transparent 50%)',
        }}
      />
      <div className="glass-panel relative z-10 p-10 w-full max-w-sm text-center">
        <div className="text-4xl mb-4">⚡</div>
        <div className="col-header mb-1">Chimera Platform</div>
        <h1 className="gradient-text text-3xl font-bold mb-1">FSU4</h1>
        <p className="text-sm mb-8" style={{ color: 'var(--text-dim)' }}>Email Intelligence Service</p>

        <div className="flex justify-center">
          <GoogleLogin
            onSuccess={handleSuccess}
            onError={() => setError('Google sign-in failed')}
            hosted_domain="ascotwm.com"
            theme="filled_black"
            shape="pill"
            text="signin_with"
          />
        </div>

        {error && (
          <p className="mt-4 text-sm" style={{ color: 'var(--red)' }}>{error}</p>
        )}

        <p className="mt-6 text-xs" style={{ color: 'var(--text-dim)', opacity: 0.5 }}>Restricted to ascotwm.com accounts</p>
      </div>
    </div>
  )
}
