import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { Empty, ErrorBox, PageTitle, Spinner } from '../ui'

const PROBLEM_LABEL = {
  bua_shortfall: 'Built-up area below norm', declared_overstated: 'Declared area overstated', oc_partial: 'OC does not cover the plan',
  survey_mismatch: 'Survey number mismatch', address_mismatch: 'Address mismatch', trust_mismatch: 'Land owner is not the trust',
  ghost_faculty: 'Ghost faculty (shared ID)', faculty_lookalike: 'Look-alike faculty, different ID', photo_reuse: 'Photo reused from another college',
  identical_file: 'Identical file from another college', fire_expired: 'Fire NOC expired', faculty_shortfall: 'Faculty below 1:20',
  declared_faculty_overstated: 'Declared faculty overstated', unqualified_faculty: 'Under-qualified faculty', cadre_shortfall: 'Cadre ratio not met',
  lease_short: 'Lease too short', affidavit_not_notarised: 'Affidavit not notarised', affidavit_intake_mismatch: 'Affidavit intake mismatch',
  missing_document: 'Mandatory document missing', no_architect_reg: 'Plan without CoA architect', core_branches: 'Fewer than 3 core branches',
  inquiry_pending: 'Inquiry pending', history_bua_shrink: 'Area shrank since last year', history_survey_change: 'Survey number changed',
  history_faculty_churn: 'Most faculty new this year', tamper_scan: 'Edited scan (pasted text)', sig_tamper: 'Signed PDF edited after signing',
  qr_mismatch: 'Printed text differs from QR', gps_far: 'Photo GPS far from campus',
}

const pct = (x) => (x == null ? '–' : `${(x * 100).toFixed(x === 1 ? 0 : 1)}%`)

export default function Evaluation() {
  const q = useQuery({ queryKey: ['evaluation'], queryFn: () => api('/api/analytics/evaluation') })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} />
  const e = q.data
  if (!e.available) return <Empty title="No evaluation yet">Run <code>python scripts/evaluate.py</code> in the backend folder.</Empty>
  const d = e.detection

  const head = [
    ['Planted problems caught', `${d.detected} of ${d.planted}`, pct(d.recall)],
    ['Flags that were correct', `${d.true_positive_codes} of ${d.true_positive_codes + d.false_positive_codes}`, pct(d.precision)],
    ['Clean applications flagged', `${e.clean_applications.with_any_flag} of ${e.clean_applications.count}`, null],
    ['Fields read correctly', `${e.extraction.correct} of ${e.extraction.total}`, pct(e.extraction.accuracy)],
    ['Right APH clause in top 5', `${Math.round(e.retrieval.recall_at_5 * e.retrieval.questions)} of ${e.retrieval.questions}`, pct(e.retrieval.recall_at_5)],
    ['Median time per dossier, end to end', `${e.timing.end_to_end_median_s ?? e.timing.median_s} s`, e.timing.end_to_end_max_s ? `max ${e.timing.end_to_end_max_s} s` : null],
  ]

  return (
    <div className="max-w-6xl">
      <PageTitle title="Evaluation" sub={`Measured on ${e.dataset.applications_scored} synthetic applications (${e.dataset.clean_applications} clean) with ${e.dataset.planted_problems} planted problems of ${e.dataset.problem_types} types. Generated ${new Date(e.generated_at).toLocaleString('en-IN')}.`} />

      <section className="panel overflow-hidden">
        <dl className="grid divide-y divide-rule sm:grid-cols-2 sm:divide-x lg:grid-cols-3">
          {head.map(([k, v, p]) => (
            <div key={k} className="px-5 py-4">
              <dt className="text-sm text-ink-soft">{k}</dt>
              <dd className="mt-1 flex items-baseline gap-3"><span className="font-cond text-2xl font-semibold tabular-nums">{v}</span>{p && <span className="text-sm text-ink-soft">{p}</span>}</dd>
            </div>
          ))}
        </dl>
      </section>

      <div className="mt-4 rounded-md border border-defic/25 bg-defic-wash px-4 py-3 text-sm text-ink">
        Read these as a test of the pipeline, not a field result. We wrote both the generator and the extractor, so labels and layouts are
        friendlier than real dossiers. Three institutions were scanned end to end to exercise OCR. Officer time saved is not measured yet; the
        protocol is: {e.officer_minutes_saved.protocol}
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-2">
        <section>
          <h2 className="text-lg font-semibold">Detection by problem type</h2>
          <table className="mt-3 w-full text-sm">
            <thead className="border-b border-rule text-left text-xs text-ink-soft"><tr><th className="py-2 font-medium">Planted problem</th><th className="font-medium">Caught</th><th className="font-medium">Right kind</th></tr></thead>
            <tbody className="divide-y divide-rule">
              {Object.entries(e.per_problem).map(([k, v]) => (
                <tr key={k}><td className="py-1.5">{PROBLEM_LABEL[k] || k}</td>
                  <td className={v.detected < v.planted ? 'text-remark font-medium' : ''}>{v.detected}/{v.planted}</td>
                  <td>{v.kind_ok}/{v.detected}</td></tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="space-y-8">
          <div>
            <h2 className="text-lg font-semibold">Wrong or extra flags</h2>
            {e.false_positives.length === 0 ? <p className="mt-2 text-sm text-ink-soft">None.</p> : (
              <ul className="mt-2 space-y-2 text-sm">
                {e.false_positives.map((f, i) => <li key={i} className="panel p-3"><span className="font-medium">{f.application}, {f.code}</span><span className="block text-ink-soft">{f.summary}</span></li>)}
              </ul>
            )}
            {e.extraction.errors.length > 0 && (
              <>
                <h3 className="mt-5 font-medium">Extraction errors</h3>
                <ul className="mt-1 text-sm text-ink-soft">{e.extraction.errors.map((x, i) => <li key={i}>{x.application}: {x.field}, expected {String(x.expected)}, read {String(x.got)}</li>)}</ul>
              </>
            )}
          </div>
          <div>
            <h2 className="text-lg font-semibold">Clause retrieval</h2>
            <p className="mt-1 text-sm text-ink-soft">{e.retrieval.questions} questions in English and Hindi, engine {e.retrieval.engine}. Top-1 {pct(e.retrieval.recall_at_1)}, top-5 {pct(e.retrieval.recall_at_5)}. {e.retrieval.note}</p>
          </div>
          <div>
            <h2 className="text-lg font-semibold">Time per tool</h2>
            <ul className="mt-2 text-sm">
              {Object.entries(e.timing.per_tool_mean_ms).map(([k, v]) => <li key={k} className="flex justify-between border-b border-rule py-1"><span>{k.replaceAll('_', ' ')}</span><span className="tabular-nums">{v} ms</span></li>)}
            </ul>
            <p className="mt-2 text-xs text-ink-soft">{e.timing.note}</p>
          </div>
        </section>
      </div>
    </div>
  )
}
