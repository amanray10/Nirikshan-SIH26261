import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api'
import { ErrorBox, PageTitle } from '../ui'

const SUGGESTED = [
  'What is the faculty student ratio for B.Tech?',
  'Can the campus land be on lease? For how many years?',
  'Can an associate professor be counted if a professor is not available?',
  'क्या भूमि पट्टे पर हो सकती है?',
  'Can an institution increase intake if an inquiry is pending?',
]

export default function Assistant() {
  const [q, setQ] = useState('')
  const ask = useMutation({ mutationFn: (question) => api('/api/aph/ask', { method: 'POST', body: { question, lang: /[ऀ-ॿ]/.test(question) ? 'hi' : 'en' } }) })
  const r = ask.data
  const go = (text) => { setQ(text); ask.mutate(text) }

  const render = (text) => text.split(/(\[[A-Z0-9.]+\])/g).map((part, i) => {
    const m = part.match(/^\[([A-Z0-9.]+)\]$/)
    return m ? <a key={i} href={`#c-${m[1]}`} className="mx-0.5 rounded bg-royal-wash px-1 text-xs font-medium text-royal">{m[1]}</a> : <span key={i}>{part}</span>
  })

  return (
    <div className="max-w-5xl">
      <PageTitle title="APH assistant" sub="Answers come only from Approval Process Handbook clauses, with the clause cited. If no clause covers the question, it says so." />
      <form onSubmit={(e) => { e.preventDefault(); if (q.trim().length > 2) ask.mutate(q) }} className="flex gap-2">
        <label htmlFor="q" className="sr-only">Question</label>
        <input id="q" className="field py-2.5 text-base" placeholder="Ask about a norm, a document or a procedure, in English or Hindi" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="btn-primary px-5" disabled={ask.isPending}>{ask.isPending ? 'Searching…' : 'Ask'}</button>
      </form>
      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTED.map((s) => (
          <button key={s} onClick={() => go(s)} className={`rounded-full border border-rule bg-sheet px-3 py-1 text-sm text-ink-soft hover:border-ruleDark hover:text-ink ${/[ऀ-ॿ]/.test(s) ? 'font-deva' : ''}`}>{s}</button>
        ))}
      </div>
      <div className="mt-4"><ErrorBox error={ask.error} /></div>

      {r && (
        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
          <section className="panel p-5">
            <h2 className="text-lg font-semibold">{r.sufficient ? 'Answer' : 'Insufficient evidence'}</h2>
            <p className="mt-2 whitespace-pre-line leading-relaxed">{render(r.answer)}</p>
            <p className="mt-4 text-xs text-ink-faint">
              Retrieved with {r.engine}; {r.generator === 'extractive' ? 'answer quoted from the top clause (no language model needed)' : r.generator === 'none' ? 'no answer generated' : `answer written by ${r.generator} from the retrieved clauses only`}.
            </p>
          </section>
          <section>
            <h2 className="text-sm font-medium text-ink-soft">Clauses retrieved</h2>
            <ol className="mt-2 space-y-3">
              {r.hits.map((h) => (
                <li key={h.clause_id} id={`c-${h.clause_id}`} className={`panel p-3 ${r.citations.includes(h.clause_id) ? 'border-royal/40' : ''}`}>
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-xs font-medium text-royal">{h.ref}</span>
                    <span className="text-xxs tabular-nums text-ink-faint">score {h.score.toFixed(2)}</span>
                  </div>
                  <p className="mt-0.5 text-sm font-medium">{h.title}</p>
                  <p className="mt-1 text-sm text-ink-soft">{h.text}</p>
                  {h.source_status !== 'verbatim' && <p className="mt-1 text-xxs text-ink-faint">{h.source_status === 'to_verify' ? 'Summary, wording to confirm' : 'Paraphrased summary'}</p>}
                </li>
              ))}
            </ol>
          </section>
        </div>
      )}
    </div>
  )
}
