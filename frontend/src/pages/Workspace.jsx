import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, openAuthed } from '../api'
import EvidenceViewer from '../components/EvidenceViewer'
import { DECISION_LABEL, DOC_LABEL, ErrorBox, KIND, KindBadge, Risk, STATUS_LABEL, Spinner, TYPE_LABEL } from '../ui'

const GROUPS = [
  ['FRAUD_SIGNAL', 'Fraud signals', 'Escalate to a committee; not sent to the institution as a fix-it item.'],
  ['DEFICIENCY', 'Deficiencies', 'Fixable gaps that go into the rectification notice.'],
  ['REVIEW_ITEM', 'Needs review', 'The system could not settle these; your judgement is needed.'],
  ['VERIFIED', 'Verified', 'Established by a signature or issuer check.'],
  ['PASS', 'Checks passed', null],
]

export default function Workspace() {
  const { id } = useParams()
  const qc = useQueryClient()
  const app = useQuery({
    queryKey: ['app', id], queryFn: () => api(`/api/applications/${id}`),
    refetchInterval: (q) => (['SUBMITTED', 'PROCESSING'].includes(q.state.data?.status) ? 2000 : false),
  })
  const findings = useQuery({ queryKey: ['findings', id], queryFn: () => api(`/api/applications/${id}/findings`) })
  const [sel, setSel] = useState(null)
  const [docId, setDocId] = useState(null)
  const [page, setPage] = useState(1)
  const [showPassed, setShowPassed] = useState(false)
  const [rightTab, setRightTab] = useState('finding')
  const [trace, setTrace] = useState(false)

  const a = app.data
  const docs = a?.documents || []
  const doc = docs.find((d) => d.id === docId) || null
  const finding = (findings.data || []).find((f) => f.id === sel) || null

  useEffect(() => {  // open the most serious finding first
    if (!sel && findings.data?.length) pick(findings.data[0])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [findings.data])
  useEffect(() => { if (!docId && docs.length) setDocId(docs[0].id) }, [docs.length])  // eslint-disable-line

  useEffect(() => {  // refresh findings once processing finishes
    if (a?.status === 'UNDER_REVIEW') qc.invalidateQueries({ queryKey: ['findings', id] })
  }, [a?.status])  // eslint-disable-line

  function pick(f) {
    setSel(f.id)
    setRightTab('finding')
    const ev = f.evidence.find((e) => e.document_id && docs.some((d) => d.id === e.document_id)) || f.evidence.find((e) => e.document_id)
    if (ev) { setDocId(ev.document_id); setPage(ev.page || 1) }
  }

  const marks = useMemo(() => {
    if (!finding || !doc) return []
    const color = KIND[finding.kind]?.ring || '#2C3E9E'
    return finding.evidence.filter((e) => e.document_id === doc.id && e.bbox)
      .map((e) => ({ page: e.page, bbox: e.bbox, color, label: e.note || (e.field || '').replaceAll('_', ' ') }))
  }, [finding, doc])

  const rerun = useMutation({
    mutationFn: () => api(`/api/applications/${id}/verify`, { method: 'POST' }),
    onSuccess: () => { setSel(null); qc.invalidateQueries({ queryKey: ['app', id] }) },
  })

  if (app.isLoading) return <Spinner />
  if (app.error) return <ErrorBox error={app.error} />

  const grouped = GROUPS.map(([k, label, hint]) => [k, label, hint, (findings.data || []).filter((f) => f.kind === k)])
  const processing = ['SUBMITTED', 'PROCESSING'].includes(a.status)
  const breakdown = a.run?.engines?.risk_breakdown || []

  return (
    <div className="-mt-2">
      {/* case header */}
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Link to="/queue" className="text-sm text-royal hover:underline">‹ Scrutiny queue</Link>
          <h1 className="mt-1 text-2xl font-semibold">{a.institution.name}</h1>
          <p className="text-sm text-ink-soft">
            {a.institution.aicte_id}. {TYPE_LABEL[a.type]} for AY {a.academic_year}, requested intake {a.requested_intake}. Ref {a.ref_no}.
          </p>
        </div>
        <div className="flex items-center gap-5">
          <div className="text-right">
            <Risk score={a.risk_score} band={a.risk_band} size="lg" />
            <p className="text-xs text-ink-soft">{a.decision ? DECISION_LABEL[a.decision] : STATUS_LABEL[a.status]}</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <button className="btn-quiet" onClick={() => rerun.mutate()} disabled={rerun.isPending || processing}>
              {processing ? 'Checking…' : 'Re-run checks'}
            </button>
            <button className="btn-quiet" onClick={() => openAuthed(`/api/applications/${id}/report?format=html`)}>Printable report</button>
            <Link to={`/applications/${id}/decision`} className="btn-primary">Notice and decision</Link>
          </div>
        </div>
      </div>
      <ErrorBox error={rerun.error} />

      {processing && (
        <div className="mb-4 flex items-center gap-3 rounded-md border border-royal/20 bg-royal-wash px-4 py-2.5 text-sm">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-royal/30 border-t-royal" />
          Running the eight checks: extraction, APH rules, cross-document, history, national cross-checks, authenticity, clause retrieval, report.
        </div>
      )}

      <div className="grid gap-4 lg:h-[calc(100vh-190px)] lg:grid-cols-[330px_minmax(0,1fr)_360px]">
        {/* findings column */}
        <section className="panel scroll-thin flex min-h-0 flex-col overflow-hidden" aria-label="Findings">
          <div className="border-b border-rule px-4 py-3">
            <p className="text-sm font-medium">Why this score</p>
            {breakdown.length === 0 && <p className="text-xs text-ink-soft">No risk points.</p>}
            <ul className="mt-1 space-y-0.5 text-xs">
              {breakdown.slice(0, 5).map((p, i) => (
                <li key={i} className="flex justify-between gap-2"><span className="truncate text-ink-soft">{p.title}</span><span className={`font-cond font-semibold ${KIND[p.kind].text}`}>+{p.points}</span></li>
              ))}
              {breakdown.length > 5 && <li className="text-ink-faint">and {breakdown.length - 5} more</li>}
            </ul>
          </div>
          <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
            {findings.isLoading && <Spinner />}
            {grouped.map(([k, label, hint, items]) => items.length > 0 && (
              <div key={k} className="border-b border-rule last:border-0">
                <button className="flex w-full items-baseline justify-between px-4 pb-1 pt-3 text-left" disabled={k !== 'PASS'}
                  onClick={() => k === 'PASS' && setShowPassed(!showPassed)}>
                  <span className={`text-sm font-semibold ${KIND[k].text}`}>{label} <span className="font-cond">{items.length}</span></span>
                  {k === 'PASS' && <span className="text-xs text-royal">{showPassed ? 'Hide' : 'Show'}</span>}
                </button>
                {hint && <p className="px-4 pb-1 text-xs text-ink-faint">{hint}</p>}
                {(k !== 'PASS' || showPassed) && (
                  <ul className="pb-2">
                    {items.map((f) => (
                      <li key={f.id}>
                        <button onClick={() => pick(f)} aria-current={sel === f.id}
                          className={`relative w-full px-4 py-2 text-left hover:bg-paper ${sel === f.id ? 'bg-paper' : ''}`}>
                          {sel === f.id && <span className={`absolute inset-y-1 left-0 w-1 rounded-r ${KIND[f.kind].bar}`} />}
                          <span className="block text-sm font-medium leading-snug">{f.title}</span>
                          <span className="mt-0.5 line-clamp-2 block text-xs text-ink-soft">{f.summary}</span>
                          {f.review_status !== 'OPEN' && <span className="mt-1 inline-block text-xxs font-medium text-royal">{f.review_status === 'ACCEPTED' ? 'Accepted by officer' : 'Overridden by officer'}</span>}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* document column */}
        <section className="panel flex min-h-[520px] flex-col overflow-hidden" aria-label="Document">
          <div className="scroll-thin flex gap-1 overflow-x-auto border-b border-rule px-2 pt-2">
            {docs.map((d) => {
              const bad = (d.authenticity?.label || '').startsWith('Suspicious')
              const good = (d.authenticity?.label || '').startsWith('Verified')
              return (
                <button key={d.id} onClick={() => { setDocId(d.id); setPage(1) }} title={d.authenticity?.label || ''}
                  className={`whitespace-nowrap rounded-t-md border border-b-0 px-3 py-1.5 text-xs ${d.id === docId ? 'border-rule bg-sheet font-medium text-ink' : 'border-transparent text-ink-soft hover:text-ink'}`}>
                  {bad && <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-remark align-middle" />}
                  {good && <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-ok align-middle" />}
                  {DOC_LABEL[d.category]}{d.category === 'campus_photo' ? ` ${d.filename.replace('campus_photo_', '').replace('.jpg', '')}` : ''}
                </button>
              )
            })}
          </div>
          <div className="min-h-0 flex-1">
            <EvidenceViewer doc={doc} page={page} onPage={setPage} marks={marks} markKey={`${sel}-${docId}-${page}`} />
          </div>
          {doc?.authenticity?.label && (
            <div className="border-t border-rule px-4 py-2 text-xs text-ink-soft">
              Authenticity: <span className="font-medium text-ink">{doc.authenticity.label}</span>. Text read from {doc.text_source || 'n/a'}.
            </div>
          )}
        </section>

        {/* detail column */}
        <section className="panel scroll-thin flex min-h-0 flex-col overflow-hidden" aria-label="Details">
          <div className="flex gap-4 border-b border-rule px-4 pt-3">
            {[['finding', 'Finding'], ['fields', 'Extracted fields'], ['trace', 'Check trace']].map(([k, l]) => (
              <button key={k} className={`tab ${rightTab === k ? 'tab-on' : ''}`} onClick={() => setRightTab(k)}>{l}</button>
            ))}
          </div>
          <div className="scroll-thin min-h-0 flex-1 overflow-y-auto p-4">
            {rightTab === 'finding' && <FindingDetail f={finding} appId={id} docs={docs} onEvidence={(e) => { setDocId(e.document_id); setPage(e.page || 1) }} />}
            {rightTab === 'fields' && <Fields doc={doc} onJump={(p) => setPage(p)} />}
            {rightTab === 'trace' && <Trace run={a.run} />}
          </div>
        </section>
      </div>
    </div>
  )
}

function FindingDetail({ f, appId, docs, onEvidence }) {
  const qc = useQueryClient()
  const [reason, setReason] = useState('')
  const [overriding, setOverriding] = useState(false)
  const review = useMutation({
    mutationFn: (decision) => api(`/api/applications/${appId}/reviews`, { method: 'POST', body: { finding_id: f.id, decision, reason } }),
    onSuccess: () => { setOverriding(false); setReason(''); qc.invalidateQueries({ queryKey: ['findings', appId] }) },
  })
  if (!f) return <p className="text-sm text-ink-soft">Select a finding to see its evidence and the APH clause behind it.</p>
  const p = f.params || {}
  return (
    <article>
      <div className="flex flex-wrap items-center gap-2">
        <KindBadge kind={f.kind} />
        <span className="text-xs text-ink-soft">{f.severity} severity, {f.code}</span>
      </div>
      <h2 className="mt-2 text-lg font-semibold leading-snug">{f.title}</h2>
      <p className="mt-2 text-sm">{f.summary}</p>

      {f.code === 'XIN-FACULTY' && f.related?.faculty && (
        <table className="mt-3 w-full text-xs">
          <thead className="text-left text-ink-soft"><tr><th className="py-1 font-medium">Faculty</th><th className="font-medium">Here</th><th className="font-medium">At {f.related.other_institution?.split(' ')[0]}</th></tr></thead>
          <tbody className="divide-y divide-rule">
            {f.related.faculty.map((x, i) => (<tr key={i}><td className="py-1">{x.name} <span className="text-ink-faint">••{x.id_last4}</span></td><td>{x.designation_here}</td><td>{x.designation_there}</td></tr>))}
          </tbody>
        </table>
      )}

      <div className="mt-4 rounded-md bg-paper p-3 text-sm">
        <p className="text-xs font-medium text-ink-soft">What this establishes</p>
        <p className="mt-0.5">{f.establishes || 'See explanation.'}</p>
      </div>

      {f.clause_ref && (
        <div className="mt-4 border-l-2 border-royal pl-3">
          <p className="text-xs font-medium text-royal">{f.clause_ref}</p>
          {f.related?.clause_title && <p className="mt-0.5 text-sm font-medium">{f.related.clause_title}</p>}
          {f.related?.clause_text && <p className="mt-1 text-sm text-ink-soft">{f.related.clause_text}</p>}
          {f.related?.clause_status && f.related.clause_status !== 'verbatim' && (
            <p className="mt-1 text-xxs text-ink-faint">{f.related.clause_status === 'to_verify' ? 'Summary; exact wording to be confirmed against the APH PDF.' : 'Paraphrased summary of the clause.'}</p>
          )}
        </div>
      )}

      {f.evidence.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-medium text-ink-soft">Evidence</p>
          <ul className="mt-1 space-y-1">
            {f.evidence.map((e, i) => {
              const d = docs.find((x) => x.id === e.document_id)
              return (
                <li key={i}>
                  {d ? (
                    <button className="w-full rounded px-2 py-1 text-left text-sm hover:bg-paper" onClick={() => onEvidence(e)}>
                      <span className="text-royal">{DOC_LABEL[e.category] || e.category}, page {e.page}</span>
                      {e.original_text && <span className="block truncate text-xs text-ink-soft">“{e.original_text}”</span>}
                    </button>
                  ) : (
                    <span className="block px-2 py-1 text-sm text-ink-soft">{DOC_LABEL[e.category] || e.category}: {e.value} {e.note && `(${e.note})`}</span>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}
      {f.related?.other_application_id && (
        <Link to={`/applications/${f.related.other_application_id}`} className="mt-3 inline-block text-sm text-royal hover:underline">
          Open {f.related.other_institution}'s application
        </Link>
      )}
      {p.photos && <p className="mt-2 text-xs text-ink-soft">Campus at {p.campus?.map((x) => x.toFixed(4)).join(', ')}.</p>}

      {f.requires_human_review && (
        <div className="mt-6 border-t border-rule pt-4">
          {f.review_status !== 'OPEN' && <p className="mb-2 text-sm font-medium text-royal">{f.review_status === 'ACCEPTED' ? 'You accepted this finding.' : 'You overrode this finding.'}</p>}
          {!overriding ? (
            <div className="flex gap-2">
              <button className="btn-primary" onClick={() => review.mutate('ACCEPT')} disabled={review.isPending}>Accept finding</button>
              <button className="btn-quiet" onClick={() => setOverriding(true)}>Override</button>
            </div>
          ) : (
            <div className="space-y-2">
              <label className="label" htmlFor="why">Reason for overriding (recorded in the audit trail)</label>
              <textarea id="why" className="field" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
              <div className="flex gap-2">
                <button className="btn-primary" onClick={() => review.mutate('OVERRIDE')} disabled={reason.trim().length < 5 || review.isPending}>Record override</button>
                <button className="btn-quiet" onClick={() => setOverriding(false)}>Cancel</button>
              </div>
            </div>
          )}
          <ErrorBox error={review.error} />
        </div>
      )}
    </article>
  )
}

function Fields({ doc, onJump }) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['fields', doc?.id], enabled: !!doc, queryFn: () => api(`/api/documents/${doc.id}/fields`) })
  const [edit, setEdit] = useState(null)
  const [val, setVal] = useState('')
  const [saved, setSaved] = useState(null)
  const save = useMutation({
    mutationFn: () => api(`/api/fields/${edit}`, { method: 'PATCH', body: { value: val, reason: 'Officer correction' } }),
    onSuccess: () => { setSaved(edit); setEdit(null); qc.invalidateQueries({ queryKey: ['fields', doc.id] }) },
  })
  if (!doc) return null
  if (q.isLoading) return <Spinner />
  if (!q.data?.length) return <p className="text-sm text-ink-soft">{doc.category === 'faculty_list' ? 'Faculty rows are stored as records (see the faculty findings).' : 'No fields extracted from this document.'}</p>
  return (
    <div>
      {saved && <p className="mb-3 rounded-md bg-ok-wash px-3 py-2 text-sm text-ok">Correction saved. Re-run checks to apply it.</p>}
      <ul className="divide-y divide-rule">
        {q.data.map((f) => (
          <li key={f.id} className="py-2">
            <div className="flex items-start justify-between gap-2">
              <button className="text-left" onClick={() => onJump(f.page)}>
                <span className="block text-xs text-ink-soft">{f.field.replaceAll('_', ' ')}, p.{f.page}</span>
                <span className={`block text-sm ${f.corrected_value != null ? 'line-through text-ink-faint' : 'font-medium'}`}>{f.value}</span>
                {f.corrected_value != null && <span className="block text-sm font-medium text-royal">{f.corrected_value}</span>}
              </button>
              <div className="flex shrink-0 items-center gap-2">
                <span className={`text-xxs tabular-nums ${f.confidence < 0.9 ? 'text-defic' : 'text-ink-faint'}`} title="OCR or parse confidence">{Math.round(f.confidence * 100)}%</span>
                {edit !== f.id && <button className="text-xs text-royal hover:underline" onClick={() => { setEdit(f.id); setVal(f.corrected_value ?? f.value) }}>Correct</button>}
              </div>
            </div>
            {edit === f.id && (
              <div className="mt-2 flex gap-2">
                <input className="field py-1" value={val} onChange={(e) => setVal(e.target.value)} aria-label={`Correct ${f.field}`} />
                <button className="btn-primary py-1" onClick={() => save.mutate()} disabled={save.isPending}>Save</button>
                <button className="btn-quiet py-1" onClick={() => setEdit(null)}>Cancel</button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Trace({ run }) {
  if (!run) return <p className="text-sm text-ink-soft">Not processed yet.</p>
  return (
    <div>
      <p className="text-sm text-ink-soft">
        One orchestrator runs a fixed list of typed tools in order; there are no free-form agent loops. Run {run.id}, {(run.duration_ms / 1000).toFixed(1)} s.
      </p>
      <ol className="mt-3 space-y-3">
        {run.tool_log.map((t, i) => (
          <li key={i} className="grid grid-cols-[22px_1fr] gap-2">
            <span className="mt-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-ink text-xxs font-semibold text-white">{i + 1}</span>
            <div>
              <p className="text-sm font-medium">{t.tool.replaceAll('_', ' ')} <span className="font-normal text-ink-faint">{t.ms} ms</span></p>
              <p className="text-xs text-ink-soft">{t.purpose}</p>
              <p className="text-xs">{t.output}</p>
            </div>
          </li>
        ))}
      </ol>
      <dl className="mt-5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 border-t border-rule pt-3 text-xs">
        <dt className="text-ink-soft">OCR</dt><dd>{run.engines?.ocr}</dd>
        <dt className="text-ink-soft">Retrieval</dt><dd>{run.engines?.retrieval}</dd>
        <dt className="text-ink-soft">Language model</dt><dd>{run.engines?.llm}</dd>
        <dt className="text-ink-soft">Rulebook</dt><dd>{run.engines?.aph_edition}</dd>
      </dl>
    </div>
  )
}
