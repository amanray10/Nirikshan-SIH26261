import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { DECISION_LABEL, DOC_LABEL, ErrorBox, KIND, KindBadge, PageTitle, STATUS_LABEL, Spinner, TYPE_LABEL } from '../ui'

export default function InstitutionApplication() {
  const { id } = useParams()
  const qc = useQueryClient()
  const app = useQuery({ queryKey: ['myapp', id], queryFn: () => api(`/api/applications/${id}`) })
  const cats = useQuery({ queryKey: ['cats'], queryFn: () => api('/api/document-categories') })
  const mine = useQuery({ queryKey: ['myapps'], queryFn: () => api('/api/applications') })
  const [result, setResult] = useState(null)
  const refresh = () => qc.invalidateQueries({ queryKey: ['myapp', id] })

  const upload = useMutation({
    mutationFn: ({ category, files }) => {
      const fd = new FormData()
      fd.append('category', category)
      for (const f of files) fd.append('files', f)
      return api(`/api/applications/${id}/documents`, { method: 'POST', form: fd })
    },
    onSuccess: refresh,
  })
  const remove = useMutation({ mutationFn: (docId) => api(`/api/documents/${docId}`, { method: 'DELETE' }), onSuccess: refresh })
  const copy = useMutation({ mutationFn: (src) => api(`/api/applications/${id}/copy-documents/${src}`, { method: 'POST' }), onSuccess: refresh })
  const check = useMutation({ mutationFn: () => api('/api/selfcheck', { method: 'POST', body: { application_id: Number(id) } }), onSuccess: (r) => { setResult(r); refresh() } })
  const submit = useMutation({ mutationFn: () => api(`/api/applications/${id}/submit`, { method: 'POST' }), onSuccess: refresh })

  if (app.isLoading || cats.isLoading) return <Spinner />
  const a = app.data
  const editable = ['DRAFT', 'SELF_CHECK'].includes(a.status)
  const required = cats.data.required[a.type] || []
  const docs = a.documents
  const earlier = (mine.data || []).filter((x) => x.id !== a.id)
  const issues = (result?.findings || []).filter((f) => ['DEFICIENCY', 'REVIEW_ITEM', 'FRAUD_SIGNAL'].includes(f.kind))
  const passed = (result?.findings || []).filter((f) => ['PASS', 'VERIFIED'].includes(f.kind))

  return (
    <div className="max-w-6xl">
      <PageTitle title={`${TYPE_LABEL[a.type]}, AY ${a.academic_year}`} back={{ to: '/institution', label: 'My applications' }}
        sub={`${a.ref_no}. Requested intake ${a.requested_intake}. Status: ${a.decision ? DECISION_LABEL[a.decision] : STATUS_LABEL[a.status]}.`}>
        {editable && <button className="btn-quiet" onClick={() => check.mutate()} disabled={check.isPending || !docs.length}>{check.isPending ? 'Checking…' : 'Run self-check'}</button>}
        {editable && <button className="btn-primary" onClick={() => submit.mutate()} disabled={submit.isPending || !docs.length}>Submit to AICTE</button>}
      </PageTitle>
      <ErrorBox error={upload.error || remove.error || copy.error || check.error || submit.error} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <section className="panel p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold">Documents</h2>
            {editable && earlier.length > 0 && (
              <button className="text-sm text-royal hover:underline" onClick={() => copy.mutate(earlier[0].id)} disabled={copy.isPending}>
                Reuse documents from {earlier[0].ref_no}
              </button>
            )}
          </div>
          <ul className="mt-3 divide-y divide-rule">
            {[...required, ...Object.keys(cats.data.categories).filter((c) => !required.includes(c))].map((c) => {
              const have = docs.filter((d) => d.category === c)
              return (
                <li key={c} className="py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium">{DOC_LABEL[c]} {required.includes(c) ? <span className="text-xs font-normal text-ink-soft">required</span> : <span className="text-xs font-normal text-ink-faint">optional</span>}</p>
                      {have.map((d) => (
                        <p key={d.id} className="flex items-center gap-2 text-sm text-ink-soft">
                          <span className="text-ok">✓</span> {d.filename}
                          {editable && <button className="text-xs text-remark hover:underline" onClick={() => remove.mutate(d.id)}>Remove</button>}
                        </p>
                      ))}
                      {!have.length && required.includes(c) && <p className="text-sm text-defic">Not uploaded</p>}
                    </div>
                    {editable && (
                      <label className="btn-quiet cursor-pointer py-1.5 text-xs">
                        {have.length ? 'Replace' : 'Upload'}
                        <input type="file" className="sr-only" accept=".pdf,.jpg,.jpeg,.png" multiple={c === 'campus_photo'}
                          onChange={(e) => e.target.files.length && upload.mutate({ category: c, files: [...e.target.files] })} />
                      </label>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
          {upload.isPending && <p className="text-sm text-ink-soft">Uploading…</p>}
        </section>

        <section className="panel p-5">
          <h2 className="text-lg font-semibold">Self-check</h2>
          {!result && (
            <p className="mt-2 text-sm text-ink-soft">
              Runs the same APH rules and document checks AICTE uses, before you submit. Nothing is sent to AICTE until you press submit.
            </p>
          )}
          {result && (
            <>
              <p className="mt-1 text-sm text-ink-soft">{issues.length ? `${issues.length} item(s) to fix or explain before submitting.` : 'No issues found in the checks that ran.'} {passed.length} checks passed.</p>
              <ul className="mt-4 space-y-3">
                {issues.map((f) => (
                  <li key={f.id} className={`rounded-md border-l-4 bg-paper p-3`} style={{ borderColor: KIND[f.kind].ring }}>
                    <div className="flex flex-wrap items-center gap-2"><KindBadge kind={f.kind} small /><span className="font-medium">{f.title}</span></div>
                    <p className="mt-1 text-sm">{f.summary}</p>
                    {f.clause_ref && <p className="mt-1 text-xs text-royal">{f.clause_ref}</p>}
                  </li>
                ))}
              </ul>
            </>
          )}
          {a.status === 'SUBMITTED' || a.status === 'UNDER_REVIEW' || a.status === 'PROCESSING' ? (
            <p className="mt-4 rounded-md bg-royal-wash px-3 py-2 text-sm">Submitted. AICTE's scrutiny is in progress; you will receive any notice here.</p>
          ) : null}
        </section>
      </div>
    </div>
  )
}
