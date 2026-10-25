import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { BAND, Counts, DECISION_LABEL, Empty, ErrorBox, Risk, STATUS_LABEL, Spinner, TYPE_LABEL } from '../ui'

export default function Queue() {
  const ov = useQuery({ queryKey: ['overview'], queryFn: () => api('/api/analytics/overview') })
  const years = ov.data?.academic_years || []
  const [year, setYear] = useState(null)
  const ay = year || years[0]
  const apps = useQuery({
    queryKey: ['apps', ay], enabled: !!ay,
    queryFn: () => api(`/api/applications?academic_year=${ay}`),
    refetchInterval: (q) => (q.state.data || []).some((a) => ['SUBMITTED', 'PROCESSING'].includes(a.status)) ? 3000 : false,
  })
  const yearOv = useQuery({ queryKey: ['overview', ay], enabled: !!ay, queryFn: () => api(`/api/analytics/overview?academic_year=${ay}`) })
  const o = yearOv.data
  const total = o ? o.risk_bands.HIGH + o.risk_bands.MEDIUM + o.risk_bands.LOW : 0
  const [filter, setFilter] = useState('ALL')
  const list = (apps.data || []).filter((a) => filter === 'ALL' || a.risk_band === filter)

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Scrutiny queue</h1>
          <p className="mt-1 text-ink-soft">Sorted by risk, so the riskiest dossiers come first and clean ones move fast.</p>
        </div>
        <div className="flex gap-4 border-b border-rule" role="tablist" aria-label="Academic year">
          {years.map((y) => (
            <button key={y} role="tab" aria-selected={y === ay} onClick={() => setYear(y)} className={`tab ${y === ay ? 'tab-on' : ''}`}>
              AY {y}
            </button>
          ))}
        </div>
      </div>

      {o && total > 0 && (
        <section className="mb-6 grid gap-6 rounded-lg border border-rule bg-sheet p-5 md:grid-cols-[1fr_auto]" aria-label="Summary">
          <div>
            <p className="text-sm text-ink-soft">
              {o.applications} applications for AY {ay}. Automated checks take about {o.avg_processing_s ?? '–'} s per dossier once its documents are read.
            </p>
            <div className="mt-3 flex h-3 overflow-hidden rounded-full bg-paper" aria-hidden>
              {['HIGH', 'MEDIUM', 'LOW'].map((b) => (
                <div key={b} className={BAND[b].bar} style={{ width: `${(o.risk_bands[b] / total) * 100}%` }} />
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-sm">
              {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map((b) => (
                <button key={b} onClick={() => setFilter(b)}
                  className={`rounded-full border px-3 py-1 ${filter === b ? 'border-ink bg-ink text-white' : 'border-rule bg-sheet hover:border-ruleDark'}`}>
                  {b === 'ALL' ? `All ${total}` : `${BAND[b].label} ${o.risk_bands[b]}`}
                </button>
              ))}
            </div>
          </div>
          <div className="min-w-[230px] md:border-l md:border-rule md:pl-6">
            <p className="text-sm font-medium">Most frequent findings</p>
            <ol className="mt-2 space-y-1 text-sm">
              {o.top_findings.slice(0, 4).map((t) => (
                <li key={t.code} className="flex justify-between gap-4"><span className="text-ink-soft">{t.title}</span><span className="font-cond font-semibold tabular-nums">{t.count}</span></li>
              ))}
            </ol>
          </div>
        </section>
      )}

      <ErrorBox error={apps.error || ov.error} />
      {(apps.isLoading || ov.isLoading) && <Spinner />}
      {apps.data && list.length === 0 && <Empty title="No applications here">Change the year or risk filter.</Empty>}

      {list.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-rule bg-sheet">
          <table className="w-full min-w-[860px] text-left">
            <thead className="border-b border-rule text-xs text-ink-soft">
              <tr>
                <th className="w-24 py-2.5 pl-5 font-medium">Risk</th>
                <th className="py-2.5 font-medium">Institution</th>
                <th className="py-2.5 font-medium">Application</th>
                <th className="py-2.5 font-medium">Findings</th>
                <th className="py-2.5 pr-5 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {list.map((a) => (
                <tr key={a.id} className="group relative hover:bg-paper/70">
                  <td className="relative py-3 pl-5">
                    <span className={`absolute inset-y-0 left-0 w-1 ${BAND[a.risk_band || '']?.bar}`} aria-hidden />
                    <Risk score={a.risk_score} band={a.risk_band} />
                  </td>
                  <td className="py-3 pr-4">
                    <Link to={`/applications/${a.id}`} className="font-medium after:absolute after:inset-0 group-hover:text-royal">
                      {a.institution?.name}
                    </Link>
                    <div className="text-xs text-ink-soft">{a.institution?.aicte_id}, {a.institution?.state}</div>
                  </td>
                  <td className="py-3 pr-4 text-sm">
                    <div>{TYPE_LABEL[a.type]}, intake {a.requested_intake}</div>
                    <div className="text-xs text-ink-soft">{a.ref_no}</div>
                  </td>
                  <td className="py-3 pr-4"><Counts counts={a.counts} /></td>
                  <td className="py-3 pr-5 text-sm">
                    {a.decision ? <span className="font-medium">{DECISION_LABEL[a.decision]}</span> : STATUS_LABEL[a.status]}
                    {a.status === 'PROCESSING' && <span className="ml-2 inline-block h-2 w-2 animate-pulse rounded-full bg-royal" />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
