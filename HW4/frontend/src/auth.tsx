import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { fetchMe, logoutRequest, type User } from './api'

type AuthState = {
  user: User | null
  setUser: (user: User | null) => void
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)
const STORAGE_KEY = 'campus-customs-user'

export function AuthProvider({ children }: { children: ReactNode }) {
  // Remember the signed-in user across reloads so the nav renders right away.
  // This is display state only (no password, no token). The real login is the
  // HttpOnly session cookie, which is checked against /api/me below.
  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as User) : null
  })

  useEffect(() => {
    if (user) localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
    else localStorage.removeItem(STORAGE_KEY)
  }, [user])

  // On load, ask the server who the session cookie belongs to. If the session
  // is gone (expired, logged out elsewhere, or a login from before sessions
  // existed), drop the stale local copy so the site shows "logged out".
  useEffect(() => {
    fetchMe()
      .then(({ user }) => setUser(user))
      .catch(() => setUser(null))
  }, [])

  const value = useMemo<AuthState>(
    () => ({
      user,
      setUser,
      logout: () => {
        setUser(null)
        logoutRequest().catch(() => {})
      },
    }),
    [user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
