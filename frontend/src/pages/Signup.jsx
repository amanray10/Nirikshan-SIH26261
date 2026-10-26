import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { ErrorBox } from '../ui'

const STATES = ['Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Goa', 'Gujarat', 'Haryana',
  'Himachal Pradesh', 'Jharkhand', 'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram',
  'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand',
  'West Bengal', 'Andaman and Nicobar Islands', 'Chandigarh', 'Dadra and Nagar Haveli and Daman and Diu', 'Delhi',
  'Jammu and Kashmir', 'Ladakh', 'Lakshadweep', 'Puducherry']

export default function Signup() {
  const { user, signup } = useAuth()
  const nav = useNavigate()
  const [f, setF] = useState({ name: '', email: '', password: '', confirm: '', institution_name: '', aicte_id: '', state: '', trust_name: '', address: '' })
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)
  if (user) return <Navigate to="/" replace />

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const pwOk = f.password.length >= 8 && /[A-Za-z]/.test(f.password) && /\d/.test(f.password)
  const match = f.password === f.confirm

  const submit = async (e) => {
    e.preventDefault()
    if (!pwOk || !match) return
    setBusy(true)
    setErr(null)
    try {
      const { confirm, ...body } = f // eslint-disable-line no-unused-vars
      await signup(body)
      nav('/institution')
    } catch (ex) { setErr(ex) } finally { setBusy(false) }
  }

  return (
    <div className="min-h-screen bg-paper px-4 py-10 sm:py-14">
      <div className="mx-auto max-w-2xl">
        <Link to="/login" className="flex w-fit items-center gap-3">
          <svg width="32" height="32" viewBox="0 0 32 32" aria-hidden><rect width="32" height="32" rx="6" fill="#1B2340" /><circle cx="16" cy="16" r="9" fill="none" stroke="#F4F6F1" strokeWidth="2.4" /><path d="M11.5 16.5l3 3 6-7" fill="none" stroke="#F4F6F1" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
          <span className="font-cond text-xl font-bold">Nirikshan</span>
        </Link>
        <h1 className="mt-8 text-3xl font-semibold">Create an institution account</h1>
        <p className="mt-2 text-ink-soft">
          For colleges applying to AICTE. You can prepare applications, run a self-check against the APH, and submit.
          Scrutiny officer accounts are issued by AICTE, not created here.
        </p>

        <form onSubmit={submit} className="panel mt-8 space-y-8 p-6 sm:p-8">
          <fieldset className="space-y-4">
            <legend className="mb-1 text-lg font-semibold">Your details</legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <div><label className="label" htmlFor="name">Full name</label><input id="name" className="field" autoComplete="name" value={f.name} onChange={set('name')} required minLength={2} /></div>
              <div><label className="label" htmlFor="email">Official email</label><input id="email" type="email" className="field" autoComplete="email" value={f.email} onChange={set('email')} required /></div>
              <div>
                <label className="label" htmlFor="pw">Password</label>
                <input id="pw" type="password" className="field" autoComplete="new-password" value={f.password} onChange={set('password')} required aria-describedby="pwhint" />
                <p id="pwhint" className={`mt-1 text-xs ${f.password && !pwOk ? 'text-defic' : 'text-ink-soft'}`}>At least 8 characters, with letters and numbers.</p>
              </div>
              <div>
                <label className="label" htmlFor="pw2">Confirm password</label>
                <input id="pw2" type="password" className="field" autoComplete="new-password" value={f.confirm} onChange={set('confirm')} required />
                {f.confirm && !match && <p className="mt-1 text-xs text-defic">Passwords don't match.</p>}
              </div>
            </div>
          </fieldset>

          <fieldset className="space-y-4">
            <legend className="mb-1 text-lg font-semibold">Institution</legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2"><label className="label" htmlFor="iname">Institution name</label><input id="iname" className="field" value={f.institution_name} onChange={set('institution_name')} required minLength={3} /></div>
              <div>
                <label className="label" htmlFor="aicte">AICTE permanent ID</label>
                <input id="aicte" className="field" placeholder="e.g. 1-12345678" value={f.aicte_id} onChange={set('aicte_id')} required pattern="[A-Za-z0-9\-/]+" />
                <p className="mt-1 text-xs text-ink-soft">One account per institution. New applicants can use their application number.</p>
              </div>
              <div>
                <label className="label" htmlFor="state">State / UT</label>
                <select id="state" className="field" value={f.state} onChange={set('state')} required>
                  <option value="">Choose</option>
                  {STATES.map((s) => <option key={s}>{s}</option>)}
                </select>
              </div>
              <div className="sm:col-span-2"><label className="label" htmlFor="trust">Trust / society / company name</label><input id="trust" className="field" value={f.trust_name} onChange={set('trust_name')} /></div>
              <div className="sm:col-span-2"><label className="label" htmlFor="addr">Campus address</label><textarea id="addr" rows={2} className="field" value={f.address} onChange={set('address')} /></div>
            </div>
          </fieldset>

          <ErrorBox error={err} />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-ink-soft">Already registered? <Link to="/login" className="font-medium text-royal hover:underline">Sign in</Link></p>
            <button className="btn-primary px-6" disabled={busy || !pwOk || !match}>{busy ? 'Creating account…' : 'Create account'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
