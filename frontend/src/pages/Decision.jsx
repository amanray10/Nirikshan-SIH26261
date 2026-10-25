import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, openAuthed } from '../api'
import { Counts, DECISION_LABEL, ErrorBox, KIND, PageTitle, Spinner, Stamp } from '../ui'

const DECISIONS = [
  ['RECTIFY', 'Issue rectification notice', 'Sends the deficiency notice to the institution.'],
  ['REFER_COMMITTEE', 'Refer to committee', 'For fraud signals that need investigation.'],
  ['SITE_VISIT', 'Order site visit', 'Expert Visit Committee checks the flagged items.'],
  ['APPROVE', 'Approve', 'No open deficiencies or fraud signals.'],
  ['REJECT', 'Reject', 'Record the grounds below.'],
]

export default function Decision() {
  const { id } = useParams()
  const qc = useQueryClient()
  const app = useQuery({ queryKey: ['app', id], queryFn: () => api(`/api/applications/${id}`) })
  const [lang, setLang] = useState('en')
  const notice = useQuery({ queryKey: ['notice', id, lang], queryFn: () => api(`/api/applications/${id}/notice?lang=${lang}`) })
  const checklist = useQuery({ queryKey: ['checklist', id], queryFn: () => api(`/api/applications/${id}/checklist`) })
  const audit = useQuery({ queryKey: ['audit', id], queryFn: () => api(`/api/applications/${id}/audit`) })
  const [body, setBody] = useState('')
  const [dirty, setDirty] = useState(false)
  const [choice, setChoice] = useState(null)
  const [reason, setReason] = useState('')
  const [stamped, setStamped] = useState(null)

  useEffect(() => { if (notice.data) { setBody(notice.data.body); setDirty(false) } }, [notice.data])

  const saveNotice = useMutation({
    mutationFn: () => api(`/api/applications/${id}/notice`, { method: 'PUT', body: { language: lang, body } }),
    onSuccess: () => { setDirty(false); qc.invalidateQueries({ queryKey: ['audit', id] }) },
  })
  const decide = useMutation({
    mutationFn: () => api(`/api/applications/${id}/reviews`, { method: 'POST', body: { decision: choice, reason } }),
    onSuccess: () => { setStamped(choice); qc.invalidateQueries({ queryKey: ['app', id] }); qc.invalidateQueries({ queryKey: ['audit', id] }); qc.invalidateQueries({ queryKey: ['apps'] }) },
  })

  if (app.isLoading) return <Spinner />
  const a = app.data
  const shown = stamped || a.decision

  return (
    <div>
      <PageTitle title="Notice and decision" back={{ to: `/applications/${id}`, label: 'Back to workspace' }}
        sub={`${a.institution.name}, ${a.ref_no}. The notice lists only deficiencies, each with its APH clause; fraud signals go to the committee instead.`}>
        <button className="btn-quiet" onClick={() => openAuthed(`/api/applications/${id}/report?format=html`)}>Printable report</button>
      </PageTitle>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <section className="panel flex flex-col">
          <div className="flex items-center justify-between border-b border-rule px-5 pt-3">
            <div className="flex gap-5" role="tablist">
              <button role="tab" aria-selected={lang === 'en'} className={`tab ${lang === 'en' ? 'tab-on' : ''}`} onClick={() => setLang('en')}>English</button>
              <button role="tab" aria-selected={lang === 'hi'} className={`tab font-deva ${lang === 'hi' ? 'tab-on' : ''}`} onClick={() => setLang('hi')}>हिन्दी</button>
            </div>
            <span className="pb-2 text-xs text-ink-soft">{notice.data?.status === 'EDITED' ? 'Edited by officer' : 'Draft generated from rule results'}</span>
          </div>
          <textarea value={body} onChange={(e) => { setBody(e.target.value); setDirty(true) }} aria-label="Notice text"
            className={`min-h-[520px] flex-1 resize-y bg-[linear-gradient(transparent_27px,#E3E8DF_28px)] bg-[length:100%_28px] bg-[position:0_16px] px-6 py-4 text-[13.5px] leading-[28px] text-ink focus:outline-none ${lang === 'hi' ? 'font-deva' : ''}`} />
          <div className="flex items-center justify-between gap-3 border-t border-rule px-5 py-3">
            <span className="text-xs text-ink-soft">Numbers in the draft come from the rule engine; edit wording freely.</span>
            <button className="btn-primary" disabled={!dirty || saveNotice.isPending} onClick={() => saveNotice.mutate()}>
              {saveNotice.isPending ? 'Saving…' : dirty ? 'Save notice' : 'Saved'}
            </button>
          </div>
        </section>

        <div className="space-y-6">
          <section className="panel relative overflow-hidden p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Record decision</h2>
                <div className="mt-1"><Counts counts={a.counts} /></div>
              </div>
              {shown && <div className="-mr-1 -mt-1"><Stamp decision={shown} key={shown} /></div>}
            </div>
            <fieldset className="mt-4 space-y-1.5">
              <legend className="sr-only">Decision</legend>
              {DECISIONS.map(([k, l, hint]) => (
                <label key={k} className={`flex cursor-pointer items-start gap-3 rounded-md border px-3 py-2 ${choice === k ? 'border-royal bg-royal-wash' : 'border-rule hover:bg-paper'}`}>
                  <input type="radio" name="decision" className="mt-1 accent-[#2C3E9E]" checked={choice === k} onChange={() => setChoice(k)} />
                  <span><span className="block text-sm font-medium">{l}</span><span className="block text-xs text-ink-soft">{hint}</span></span>
                </label>
              ))}
            </fieldset>
            <label className="label mt-4" htmlFor="reason">Remarks for the file</label>
            <textarea id="reason" className="field" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
            <ErrorBox error={decide.error} />
            <button className="btn-primary mt-3 w-full" disabled={!choice || decide.isPending} onClick={() => decide.mutate()}>
              {choice ? `Record: ${DECISION_LABEL[choice]}` : 'Choose a decision'}
            </button>
          </section>

          <section className="panel p-5">
            <h2 className="text-lg font-semibold">Site-visit checklist</h2>
            <p className="text-sm text-ink-soft">Targeted at what the checks flagged, for the Expert Visit Committee.</p>
            {checklist.data?.length === 0 && <p className="mt-3 text-sm">Nothing flagged for a site visit.</p>}
            <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm marker:text-ink-faint">
              {(checklist.data || []).map((c) => (
                <li key={c.code}><span className={KIND[c.kind]?.text}>{c.item}</span></li>
              ))}
            </ol>
          </section>

          <section className="panel p-5">
            <h2 className="text-lg font-semibold">Audit trail</h2>
            <ol className="mt-3 space-y-2 border-l border-rule pl-4">
              {(audit.data || []).slice(0, 14).map((e) => (
                <li key={e.id} className="relative text-sm">
                  <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-ruleDark" />
                  <span className="font-medium">{e.action.replaceAll('_', ' ')}</span>
                  {e.details?.decision && <span>: {e.details.decision.toLowerCase().replaceAll('_', ' ')}</span>}
                  <span className="block text-xs text-ink-soft">{e.user}, {new Date(e.created_at + 'Z').toLocaleString('en-IN')}</span>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </div>
    </div>
  )
}
