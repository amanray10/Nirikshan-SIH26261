import { useEffect, useRef, useState } from 'react'
import { pageImage } from '../api'
import { DOC_LABEL } from '../ui'

/**
 * Shows one page of an uploaded document with evidence regions drawn on top.
 * Every bbox is in PDF points; the backend reports the page size in the same space.
 */
export default function EvidenceViewer({ doc, page, onPage, marks = [], markKey }) {
  const [img, setImg] = useState(null)
  const [err, setErr] = useState(null)
  const box = useRef(null)
  const [width, setWidth] = useState(0)

  useEffect(() => {
    if (!doc) return
    let url
    let live = true
    setImg(null)
    setErr(null)
    pageImage(doc.id, page).then((r) => { url = r.url; if (live) setImg(r) }).catch((e) => live && setErr(e))
    return () => { live = false; if (url) URL.revokeObjectURL(url) }
  }, [doc?.id, page])

  useEffect(() => {
    if (!box.current) return
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width))
    ro.observe(box.current)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {  // scroll the first mark into view
    const el = box.current?.querySelector('[data-mark]')
    el?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [img, markKey])

  if (!doc) return <div className="flex h-full items-center justify-center p-10 text-sm text-ink-soft">Select a document or a finding.</div>
  const scale = img && width ? width / img.w : 0
  const pages = doc.page_count || 1

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-3 border-b border-rule px-4 py-2 text-sm">
        <div className="min-w-0">
          <span className="font-medium">{DOC_LABEL[doc.category] || doc.category}</span>
          <span className="ml-2 truncate text-xs text-ink-soft">{doc.filename}</span>
        </div>
        <div className="flex items-center gap-1">
          <button className="btn-quiet px-2 py-1" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">‹</button>
          <span className="w-16 text-center text-xs tabular-nums text-ink-soft">Page {page} / {pages}</span>
          <button className="btn-quiet px-2 py-1" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page">›</button>
        </div>
      </div>
      <div className="scroll-thin flex-1 overflow-auto bg-[#E6EAE2] p-4">
        <div ref={box} className="relative mx-auto max-w-[760px] bg-white shadow-[0_1px_0_#C9D0C4,0_6px_18px_-8px_rgba(27,35,64,0.25)]">
          {err && <p className="p-6 text-sm text-remark">{String(err.message)}</p>}
          {!img && !err && <div className="aspect-[1/1.41] animate-pulse bg-white" />}
          {img && <img src={img.url} alt={`${DOC_LABEL[doc.category]} page ${page}`} className="block w-full" draggable={false} />}
          {img && scale > 0 && marks.filter((m) => m.page === page && m.bbox).map((m, i) => (
            <div key={`${markKey}-${i}`} data-mark className="mark-draw pointer-events-none absolute rounded-[3px]"
              style={{
                left: m.bbox[0] * scale - 4, top: m.bbox[1] * scale - 3,
                width: (m.bbox[2] - m.bbox[0]) * scale + 8, height: (m.bbox[3] - m.bbox[1]) * scale + 6,
                border: `2px solid ${m.color}`, background: `${m.color}14`, animationDelay: `${i * 90}ms`,
              }}>
              {m.label && (
                <span className="absolute -top-5 left-0 whitespace-nowrap rounded-sm px-1 text-xxs font-medium text-white" style={{ background: m.color }}>
                  {m.label}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
