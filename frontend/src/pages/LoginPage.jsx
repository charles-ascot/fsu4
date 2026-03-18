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
    <div className="min-h-screen bg-surface flex items-center justify-center">
      <div className="bg-panel border border-border rounded-2xl p-10 w-full max-w-sm text-center">
        <div className="text-4xl mb-4">⚡</div>
        <div className="text-xs font-semibold tracking-widest text-muted uppercase mb-1">Chimera Platform</div>
        <h1 className="text-2xl font-bold text-white mb-1">FSU4</h1>
        <p className="text-sm text-muted mb-8">Email Intelligence Service</p>

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
          <p className="mt-4 text-sm text-red-400">{error}</p>
        )}

        <p className="mt-6 text-xs text-muted">Restricted to ascotwm.com accounts</p>
      </div>
    </div>
  )
}
