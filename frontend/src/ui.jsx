import { Link } from 'react-router-dom'

export const KIND = {
  FRAUD_SIGNAL: { label: 'Fraud signal', text: 'text-remark', bg: 'bg-remark-wash', bar: 'bg-remark', ring: '#B3261E' },
  DEFICIENCY: { label: 'Deficiency', text: 'text-defic', bg: 'bg-defic-wash', bar: 'bg-defic', ring: '#9A5600' },
  REVIEW_ITEM: { label: 'Needs review', text: 'text-review', bg: 'bg-review-wash', bar: 'bg-review', ring: '#2F5E8C' },
  VERIFIED: { label: 'Verified', text: 'text-ok', bg: 'bg-ok-wash', bar: 'bg-ok', ring: '#2E6B3F' },
  PASS: { label: 'Passed', text: 'text-ink-soft', bg: 'bg-paper', bar: 'bg-ruleDark', ring: '#7C8396' },
}

export const BAND = {
  HIGH: { label: 'High risk', text: 'text-remark', bar: 'bg-remark' },
  MEDIUM: { label: 'Medium risk', text: 'text-defic', bar: 'bg-defic' },
  LOW: { label: 'Low risk', text: 'text-ok', bar: 'bg-ok' },
  '': { label: 'Not scored', text: 'text-ink-faint', bar: 'bg-rule' },
}

export const DOC_LABEL = {
  land_deed: 'Land deed', building_plan: 'Building plan', occupancy_certificate: 'Occupancy certificate',
  fire_noc: 'Fire safety NOC', affidavit: 'Affidavit', trust_registration: 'Trust registration',
  faculty_list: 'Faculty list', campus_photo: 'Campus photo',
}

export const TYPE_LABEL = { EOA: 'Extension of approval', INTAKE_INCREASE: 'Increase in intake', NEW_INSTITUTION: 'New institution' }

export const STATUS_LABEL = {
  DRAFT: 'Draft', SELF_CHECK: 'Self-checked', SUBMITTED: 'Submitted', PROCESSING: 'Processing',
  UNDER_REVIEW: 'Under review', DECIDED: 'Decided',
}

export const DECISION_LABEL = {
  APPROVE: 'Approved', REJECT: 'Rejected', RECTIFY: 'Rectification notice issued',
  REFER_COMMITTEE: 'Referred to committee', SITE_VISIT: 'Site visit ordered',
}

export function KindBadge({ kind, small }) {
  const k = KIND[kind] || KIND.PASS
  return (
    <span className={`inline-flex items-center gap-1.5 rounded px-1.5 ${small ? 'py-0 text-xxs' : 'py-0.5 text-xs'} font-medium ${k.bg} ${k.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${k.bar}`} aria-hidden />
      {k.label}
    </span>
  )
}

export function Risk({ score, band, size = 'md' }) {
  const b = BAND[band || ''] || BAND['']
  const big = size === 'lg'
  return (
    <div className="flex items-baseline gap-2">
      <span className={`font-cond font-bold tabular-nums leading-none ${b.text} ${big ? 'text-4xl' : 'text-2xl'}`}>
        {band ? Math.round(score) : '–'}
      </span>
      {big && <span className={`text-sm font-medium ${b.text}`}>{b.label}</span>}
    </div>
  )
}

export function Spinner({ label = 'Loading' }) {
  return (
    <div role="status" className="flex items-center gap-2 py-10 text-sm text-ink-soft">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-rule border-t-royal" aria-hidden />
      {label}…
    </div>
  )
}

export function ErrorBox({ error }) {
  if (!error) return null
  return <div className="rounded-md border border-remark/30 bg-remark-wash px-3 py-2 text-sm text-remark">{String(error.message || error)}</div>
}

export function Empty({ title, children }) {
  return (
    <div className="rounded-lg border border-dashed border-ruleDark px-6 py-10 text-center">
      <p className="font-medium">{title}</p>
      {children && <div className="mt-1 text-sm text-ink-soft">{children}</div>}
    </div>
  )
}

export function PageTitle({ title, sub, back, children }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        {back && <Link to={back.to} className="mb-1 inline-block text-sm text-royal hover:underline">‹ {back.label}</Link>}
        <h1 className="text-2xl font-semibold">{title}</h1>
        {sub && <p className="mt-1 max-w-3xl text-ink-soft">{sub}</p>}
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </div>
  )
}

export function Counts({ counts }) {
  const items = [['FRAUD_SIGNAL', 'fraud'], ['DEFICIENCY', 'defic.'], ['REVIEW_ITEM', 'review']]
  return (
    <div className="flex gap-3 text-xs">
      {items.map(([k, l]) => (
        <span key={k} className={(counts?.[k] || 0) ? KIND[k].text + ' font-medium' : 'text-ink-faint'}>
          <span className="font-cond text-sm font-semibold tabular-nums">{counts?.[k] || 0}</span> {l}
        </span>
      ))}
    </div>
  )
}

export function Stamp({ decision }) {
  if (!decision) return null
  const red = ['REJECT', 'REFER_COMMITTEE'].includes(decision)
  const color = red ? '#B3261E' : decision === 'APPROVE' ? '#2E6B3F' : '#2C3E9E'
  return (
    <div className="stamp-in pointer-events-none select-none" style={{ transform: 'rotate(-8deg)' }} aria-label={DECISION_LABEL[decision]}>
      <div className="rounded-md border-[3px] px-4 py-1.5 text-center font-cond font-bold tracking-wide"
        style={{ borderColor: color, color, boxShadow: `inset 0 0 0 2px ${color}22` }}>
        <div className="text-lg leading-tight">{DECISION_LABEL[decision]}</div>
        <div className="text-xxs font-medium opacity-80">Scrutiny officer, {new Date().toLocaleDateString('en-IN')}</div>
      </div>
    </div>
  )
}
