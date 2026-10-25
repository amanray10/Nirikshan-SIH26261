import { createContext, useContext, useState } from 'react'
import { api, getSession, setSession } from './api'

const Ctx = createContext(null)

export function AuthProvider({ children }) {
  const [session, setS] = useState(getSession())
  const login = async (email, password) => {
    const s = await api('/api/auth/login', { method: 'POST', body: { email, password } })
    setSession(s)
    setS(s)
    return s
  }
  const logout = () => { setSession(null); setS(null) }
  return <Ctx.Provider value={{ session, user: session?.user, institution: session?.institution, login, logout }}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)
