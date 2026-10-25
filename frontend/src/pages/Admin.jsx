import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { ErrorBox, PageTitle, Spinner, TYPE_LABEL } from '../ui'

export default function Admin() {
  const qc = useQueryClient()
  const rules = useQuery({ queryKey: ['rules'], queryFn: () => api('/api/rules') })
  const norms = useQuery({ queryKey: ['norms'], queryFn: () => api('/api/norms') })
  const engines = useQuery({ queryKey: ['engines'], queryFn: () => api('/api/analytics/engines') })
  const toggle = useMutation({
    mutationFn: ({ code, enabled }) => api(`/api/rules/${code}`, { method: 'PATCH', body: { enabled } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rules'] }),
  })
  const [edit, setEdit] = useState({})
  const saveNorm = useMutation({
    mutationFn: (n) => api(`/api/norms/${n.id}`, { method: 'PATCH', body: { value: Number(edit[n.id]), source_status: 'verified' } }),
    onSuccess: (_, n) => { setEdit((e) => { const c = { ...e }; delete c[n.id]; return c }); qc.invalidateQueries({ queryKey: ['norms'] }) },
  })

  return (
    <div className="max-w-6xl">
      <PageTitle title="Rules and norms" sub="The APH as code. Norm values are data, rules are versioned functions with unit tests, and every change is written to the audit log." />
      {engines.data && (
        <p className="mb-6 text-sm text-ink-soft">
          Running offline with OCR <b className="text-ink">{engines.data.ocr}</b>, retrieval <b className="text-ink">{engines.data.retrieval}</b>,
          language model <b className="text-ink">{engines.data.llm}</b>, database <b className="text-ink">{engines.data.database}</b>, rulebook <b className="text-ink">{engines.data.aph_edition}</b>.
        </p>
      )}
      <ErrorBox error={toggle.error || saveNorm.error} />

      <section>
        <h2 className="text-lg font-semibold">Norm table</h2>
        <p className="text-sm text-ink-soft">Values marked “to verify” are placeholders until copied from the official APH PDF. Saving a value marks it verified.</p>
        {norms.isLoading ? <Spinner /> : (
          <div className="mt-3 overflow-x-auto rounded-lg border border-rule bg-sheet">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="border-b border-rule text-left text-xs text-ink-soft"><tr><th className="px-4 py-2 font-medium">Norm</th><th className="font-medium">Programme</th><th className="font-medium">Value</th><th className="font-medium">Source</th><th className="pr-4 font-medium">Status</th></tr></thead>
              <tbody className="divide-y divide-rule">
                {norms.data.map((n) => (
                  <tr key={n.id}>
                    <td className="px-4 py-2"><span className="font-medium">{n.norm_name.replaceAll('_', ' ')}</span>{n.note && <span className="block text-xs text-ink-soft">{n.note}</span>}</td>
                    <td className="text-ink-soft">{n.program}</td>
                    <td>
                      <div className="flex items-center gap-1.5">
                        <input className="field w-24 py-1" value={edit[n.id] ?? n.value} onChange={(e) => setEdit({ ...edit, [n.id]: e.target.value })} aria-label={`Value for ${n.norm_name}`} />
                        {edit[n.id] !== undefined && <button className="btn-primary px-2 py-1 text-xs" onClick={() => saveNorm.mutate(n)}>Save</button>}
                      </div>
                      <span className="text-xxs text-ink-faint">{n.unit}</span>
                    </td>
                    <td className="text-xs">{n.clause_ref}</td>
                    <td className="pr-4"><span className={`rounded px-1.5 py-0.5 text-xs ${n.source_status === 'verified' ? 'bg-ok-wash text-ok' : 'bg-defic-wash text-defic'}`}>{n.source_status === 'verified' ? 'Verified' : 'To verify'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-semibold">Rule registry</h2>
        {rules.isLoading ? <Spinner /> : (
          <ul className="mt-3 divide-y divide-rule rounded-lg border border-rule bg-sheet">
            {rules.data.map((r) => (
              <li key={r.rule_code} className="flex flex-wrap items-start justify-between gap-4 px-4 py-3">
                <div className="min-w-0 max-w-3xl">
                  <p className="font-medium">{r.title} <span className="text-xs font-normal text-ink-faint">{r.rule_code} v{r.version}</span></p>
                  <p className="text-sm text-ink-soft">{r.description}</p>
                  <p className="mt-0.5 text-xs text-royal">{r.clause_ref}. Applies to {r.applies_to.map((t) => TYPE_LABEL[t]).join(', ').toLowerCase()}.</p>
                </div>
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <input type="checkbox" className="h-4 w-4 accent-[#2C3E9E]" checked={r.enabled} onChange={(e) => toggle.mutate({ code: r.rule_code, enabled: e.target.checked })} />
                  {r.enabled ? 'Enabled' : 'Disabled'}
                </label>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
