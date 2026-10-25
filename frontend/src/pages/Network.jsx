import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { BAND, ErrorBox, PageTitle, Spinner } from '../ui'

const EDGE = {
  'XIN-FACULTY': { label: 'Shared faculty', color: '#B3261E', dash: '' },
  'XIN-PHOTO': { label: 'Reused photo', color: '#9A5600', dash: '6 4' },
  'XIN-FILE': { label: 'Identical file', color: '#2C3E9E', dash: '2 4' },
  'XIN-LOOKALIKE': { label: 'Look-alike faculty', color: '#2F5E8C', dash: '1 5' },
}

// Rough outline positions: institutions are placed by their real latitude/longitude on an India-shaped frame.
const LAT = [6.5, 35.5]
const LON = [68, 97.5]

export default function Network() {
  const ov = useQuery({ queryKey: ['overview'], queryFn: () => api('/api/analytics/overview') })
  const ay = ov.data?.academic_years?.[0]
  const net = useQuery({ queryKey: ['network', ay], enabled: !!ay, queryFn: () => api(`/api/analytics/network?academic_year=${ay}`) })
  const [hover, setHover] = useState(null)

  const W = 560, H = 620
  const pos = useMemo(() => {
    const p = {}
    for (const n of net.data?.nodes || []) {
      p[n.id] = { x: ((n.lon - LON[0]) / (LON[1] - LON[0])) * W, y: H - ((n.lat - LAT[0]) / (LAT[1] - LAT[0])) * H }
    }
    return p
  }, [net.data])

  if (net.isLoading || ov.isLoading) return <Spinner />
  const nodes = net.data?.nodes || []
  const edges = net.data?.edges || []
  const linked = new Set(edges.flatMap((e) => [e.source, e.target]))

  return (
    <div>
      <PageTitle title="National view" sub={`Links between institutions found by comparing every dossier submitted for AY ${ay}. A single scrutiny officer, looking at one file, cannot see these.`} />
      <ErrorBox error={net.error} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,620px)_1fr]">
        <figure className="panel p-4">
          <svg viewBox={`-20 -20 ${W + 40} ${H + 40}`} className="w-full" role="img" aria-label="Map of institutions and the links between them">
            {/* faint latitude rules */}
            {[10, 15, 20, 25, 30].map((lat) => {
              const y = H - ((lat - LAT[0]) / (LAT[1] - LAT[0])) * H
              return <g key={lat}><line x1={0} x2={W} y1={y} y2={y} stroke="#E3E8DF" /><text x={W} y={y - 4} textAnchor="end" fontSize="10" fill="#9AA0AE">{lat}°N</text></g>
            })}
            {edges.map((e, i) => {
              const a = pos[e.source], b = pos[e.target]
              if (!a || !b) return null
              const s = EDGE[e.type]
              const mx = (a.x + b.x) / 2 + (a.y - b.y) * 0.18, my = (a.y + b.y) / 2 + (b.x - a.x) * 0.18
              return <path key={i} d={`M${a.x},${a.y} Q${mx},${my} ${b.x},${b.y}`} fill="none" stroke={s.color} strokeWidth={1.5 + Math.min(e.weight, 4)} strokeDasharray={s.dash} opacity={hover && ![e.source, e.target].includes(hover) ? 0.15 : 0.9} />
            })}
            {nodes.map((n) => {
              const p = pos[n.id]
              const c = { HIGH: '#B3261E', MEDIUM: '#9A5600', LOW: '#2E6B3F' }[n.risk_band] || '#7C8396'
              const on = linked.has(n.id)
              return (
                <g key={n.id} onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)}>
                  <circle cx={p.x} cy={p.y} r={on ? 8 : 5} fill={on ? c : '#fff'} stroke={c} strokeWidth={2} />
                  {(on || hover === n.id) && (
                    <text x={p.x + 12} y={p.y + 4} fontSize="12" fill="#1B2340" fontWeight={on ? 600 : 400} paintOrder="stroke" stroke="#fff" strokeWidth="3">{n.name.split(' ').slice(0, 2).join(' ')}</text>
                  )}
                </g>
              )
            })}
          </svg>
          <figcaption className="mt-2 flex flex-wrap gap-4 text-xs text-ink-soft">
            {Object.entries(EDGE).map(([k, s]) => (
              <span key={k} className="flex items-center gap-1.5"><svg width="26" height="6"><line x1="0" x2="26" y1="3" y2="3" stroke={s.color} strokeWidth="2.5" strokeDasharray={s.dash} /></svg>{s.label}</span>
            ))}
            <span>Filled dot: institution with a cross-institution link. Positions use campus coordinates.</span>
          </figcaption>
        </figure>

        <section>
          <h2 className="text-lg font-semibold">{edges.length} links across {linked.size} institutions</h2>
          {edges.length === 0 && <p className="mt-2 text-ink-soft">No cross-institution links found for this year.</p>}
          <ul className="mt-3 space-y-3">
            {edges.map((e, i) => {
              const a = nodes.find((n) => n.id === e.source), b = nodes.find((n) => n.id === e.target)
              return (
                <li key={i} className="panel p-4" onMouseEnter={() => setHover(e.source)} onMouseLeave={() => setHover(null)}>
                  <p className="text-sm font-medium" style={{ color: EDGE[e.type].color }}>{EDGE[e.type].label}</p>
                  <p className="mt-0.5 font-medium">{a?.name} and {b?.name}</p>
                  <p className="mt-1 text-sm text-ink-soft">{e.detail}</p>
                  <Link to={`/applications/${e.application_id}`} className="mt-2 inline-block text-sm text-royal hover:underline">Open the flagged application</Link>
                </li>
              )
            })}
          </ul>
          <p className="mt-6 text-sm text-ink-soft">
            Faculty are matched on a salted hash of their PAN or Aadhaar, never the raw number. Photos are matched on perceptual hashes,
            which survive resizing and recompression. Each link is a screening signal for the committee, not proof.
          </p>
          <div className="mt-4 flex flex-wrap gap-3 text-xs">
            {['HIGH', 'MEDIUM', 'LOW'].map((b) => <span key={b} className={BAND[b].text}>● {BAND[b].label}</span>)}
          </div>
        </section>
      </div>
    </div>
  )
}
