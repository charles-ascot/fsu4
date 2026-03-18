import { createContext, useContext, useState, useCallback } from 'react'
import { jwtDecode } from 'jwt-decode'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const stored = sessionStorage.getItem('fsu4_user')
      return stored ? JSON.parse(stored) : null
    } catch {
      return null
    }
  })

  const login = useCallback((credentialResponse) => {
    const decoded = jwtDecode(credentialResponse.credential)
    if (decoded.hd !== 'ascotwm.com') {
      throw new Error('Access restricted to ascotwm.com accounts')
    }
    const u = { name: decoded.name, email: decoded.email, picture: decoded.picture }
    sessionStorage.setItem('fsu4_user', JSON.stringify(u))
    setUser(u)
  }, [])

  const logout = useCallback(() => {
    sessionStorage.removeItem('fsu4_user')
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
