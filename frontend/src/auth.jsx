import { createContext, useContext, useState } from 'react'
import { api, getSession, setSession } from './api'

const Ctx = createContext(null)

export function AuthProvider({ children }) {
  const [session, setS] = useState(getSession())
  const save = (s) => { setSession(s); setS(s); return s }

  const login = async (email, password) => save(await api('/api/auth/login', { method: 'POST', body: { email, password } }))
  const signup = async (form) => save(await api('/api/auth/signup', { method: 'POST', body: form }))
  const logout = () => { setSession(null); setS(null) }

  return (
    <Ctx.Provider value={{ session, user: session?.user, institution: session?.institution, login, signup, logout }}>
      {children}
    </Ctx.Provider>
  )
}

export const useAuth = () => useContext(Ctx)
