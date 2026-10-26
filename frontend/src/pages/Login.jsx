import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { ErrorBox } from '../ui'

const DEMO = [
  { email: 'officer@nirikshan.demo', password: 'officer123', who: 'Scrutiny officer', note: 'Risk-sorted queue, evidence, decisions' },
  { email: 'admin@nirikshan.demo', password: 'admin123', who: 'Administrator', note: 'APH rules and norm table' },
  { email: 'i05@college.demo', password: 'college123', who: 'Institution', note: 'Self-check before submitting' },
]

export default function Login() {
  const { user, login } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  if (user) return <Navigate to="/" replace />

  const submit = async (e, creds) => {
    e?.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      const s = await login(creds?.email ?? email, creds?.password ?? password)
      nav(s.user.role === 'institution' ? '/institution' : '/queue')
    } catch (ex) { setErr(ex) } finally { setBusy(false) }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="noting relative flex flex-col justify-between overflow-hidden bg-sheet px-6 py-10 sm:px-14 lg:py-14">
        <div className="flex items-center gap-3">
          <svg width="36" height="36" viewBox="0 0 32 32" aria-hidden><rect width="32" height="32" rx="6" fill="#1B2340" /><circle cx="16" cy="16" r="9" fill="none" stroke="#F4F6F1" strokeWidth="2.4" /><path d="M11.5 16.5l3 3 6-7" fill="none" stroke="#F4F6F1" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
          <span className="font-cond text-xl font-bold">Nirikshan <span className="font-deva font-normal text-ink-soft">निरीक्षण</span></span>
        </div>
        <div className="my-12 max-w-xl pl-0 lg:pl-6">
          <h1 className="text-4xl font-semibold leading-[1.1] sm:text-5xl">Check an approval dossier against the APH in minutes, with every finding pinned to its page.</h1>
          <p className="mt-5 max-w-lg text-lg text-ink-soft">
            Nirikshan reads the institution's documents, applies the Approval Process Handbook as code, and looks across every
            institution for shared faculty and recycled photos. The scrutiny officer decides.
          </p>
          <dl className="mt-10 grid max-w-lg grid-cols-3 gap-6 border-t border-rule pt-6 text-sm">
            <div><dt className="text-ink-soft">APH rules as code</dt><dd className="font-cond text-2xl font-semibold">14</dd></div>
            <div><dt className="text-ink-soft">Authenticity levels</dt><dd className="font-cond text-2xl font-semibold">4</dd></div>
            <div><dt className="text-ink-soft">Cloud calls</dt><dd className="font-cond text-2xl font-semibold">0</dd></div>
          </dl>
        </div>
        <p className="text-xs text-ink-faint">SIH 2026, problem statement 26261. Prototype running on synthetic, fictional dossiers.</p>
      </section>

      <section className="flex items-center justify-center bg-paper px-6 py-12">
        <div className="w-full max-w-sm">
          <h2 className="text-2xl font-semibold">Sign in</h2>
          <form onSubmit={submit} className="mt-6 space-y-4">
            <div>
              <label className="label" htmlFor="email">Email</label>
              <input id="email" className="field" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div>
              <label className="label" htmlFor="pw">Password</label>
              <input id="pw" className="field" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <ErrorBox error={err} />
            <button className="btn-primary w-full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
          </form>
          <p className="mt-4 text-sm text-ink-soft">
            New institution? <Link to="/signup" className="font-medium text-royal hover:underline">Create an account</Link>
          </p>
          <div className="mt-10">
            <p className="text-sm font-medium">Demo accounts</p>
            <ul className="mt-2 divide-y divide-rule rounded-lg border border-rule bg-sheet">
              {DEMO.map((d) => (
                <li key={d.email}>
                  <button type="button" onClick={(e) => submit(e, d)} disabled={busy}
                    className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-paper">
                    <span>
                      <span className="block font-medium">{d.who}</span>
                      <span className="block text-xs text-ink-soft">{d.note}</span>
                    </span>
                    <span className="text-xs text-royal">Use</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>
    </div>
  )
}
