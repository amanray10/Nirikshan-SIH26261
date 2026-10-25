import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { useAuth } from '../auth'
import { DECISION_LABEL, Empty, ErrorBox, PageTitle, STATUS_LABEL, Spinner, TYPE_LABEL } from '../ui'

const DEFAULT_COURSES = [
  { name: 'Computer Science & Engineering', existing_intake: 60, intake: 120, core: true },
  { name: 'Mechanical Engineering', existing_intake: 60, intake: 60, core: true },
  { name: 'Civil Engineering', existing_intake: 60, intake: 60, core: true },
  { name: 'Electrical Engineering', existing_intake: 60, intake: 60, core: true },
  { name: 'Artificial Intelligence & Data Science', existing_intake: 60, intake: 60, core: false },
]

export default function InstitutionHome() {
  const { institution } = useAuth()
  const nav = useNavigate()
  const apps = useQuery({ queryKey: ['myapps'], queryFn: () => api('/api/applications') })
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ type: 'INTAKE_INCREASE', academic_year: '2027-28', built_up_area_sqm: '', land_area_acres: '', faculty_count: '', avg_admission_ratio: '0.85' })
  const [courses, setCourses] = useState(DEFAULT_COURSES)
  const total = courses.reduce((s, c) => s + Number(c.intake || 0), 0)

  const create = useMutation({
    mutationFn: () => api('/api/applications', {
      method: 'POST',
      body: {
        type: form.type, academic_year: form.academic_year, requested_intake: total,
        declared: {
          courses: courses.map((c) => ({ ...c, intake: Number(c.intake), existing_intake: Number(c.existing_intake) })),
          built_up_area_sqm: Number(form.built_up_area_sqm) || undefined, land_area_acres: Number(form.land_area_acres) || undefined,
          faculty_count: Number(form.faculty_count) || undefined, avg_admission_ratio: Number(form.avg_admission_ratio) || undefined,
          trust_name: institution?.trust_name, investigation_pending: false,
        },
      },
    }),
    onSuccess: (a) => nav(`/institution/applications/${a.id}`),
  })
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  return (
    <div className="max-w-5xl">
      <PageTitle title={institution?.name || 'My applications'} sub="Prepare an application, run the same checks AICTE runs, fix what they find, then submit.">
        <button className="btn-primary" onClick={() => setOpen(!open)}>{open ? 'Close form' : 'Start an application'}</button>
      </PageTitle>

      {open && (
        <form className="panel mb-8 p-5" onSubmit={(e) => { e.preventDefault(); create.mutate() }}>
          <h2 className="text-lg font-semibold">New application</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <div><label className="label" htmlFor="t">Type</label>
              <select id="t" className="field" value={form.type} onChange={set('type')}>
                {Object.entries(TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select></div>
            <div><label className="label" htmlFor="ay">Academic year</label><input id="ay" className="field" value={form.academic_year} onChange={set('academic_year')} pattern="\d{4}-\d{2}" /></div>
            <div><label className="label">Total intake requested</label><p className="py-2 font-cond text-xl font-semibold">{total}</p></div>
            <div><label className="label" htmlFor="bua">Built-up area (sq.m)</label><input id="bua" className="field" inputMode="decimal" value={form.built_up_area_sqm} onChange={set('built_up_area_sqm')} /></div>
            <div><label className="label" htmlFor="land">Land area (acres)</label><input id="land" className="field" inputMode="decimal" value={form.land_area_acres} onChange={set('land_area_acres')} /></div>
            <div><label className="label" htmlFor="fac">Teaching faculty in position</label><input id="fac" className="field" inputMode="numeric" value={form.faculty_count} onChange={set('faculty_count')} /></div>
          </div>
          <h3 className="mt-6 text-sm font-medium">Courses</h3>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead className="text-left text-xs text-ink-soft"><tr><th className="py-1 font-medium">Course</th><th className="font-medium">Approved intake</th><th className="font-medium">Requested intake</th><th className="font-medium">Core branch</th></tr></thead>
              <tbody>
                {courses.map((c, i) => (
                  <tr key={i}>
                    <td className="py-1 pr-2"><input className="field py-1" value={c.name} onChange={(e) => setCourses(courses.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} aria-label="Course name" /></td>
                    <td className="pr-2"><input className="field w-24 py-1" value={c.existing_intake} onChange={(e) => setCourses(courses.map((x, j) => j === i ? { ...x, existing_intake: e.target.value } : x))} aria-label="Approved intake" /></td>
                    <td className="pr-2"><input className="field w-24 py-1" value={c.intake} onChange={(e) => setCourses(courses.map((x, j) => j === i ? { ...x, intake: e.target.value } : x))} aria-label="Requested intake" /></td>
                    <td><input type="checkbox" className="h-4 w-4 accent-[#2C3E9E]" checked={c.core} onChange={(e) => setCourses(courses.map((x, j) => j === i ? { ...x, core: e.target.checked } : x))} aria-label="Core branch" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ErrorBox error={create.error} />
          <button className="btn-primary mt-5" disabled={create.isPending}>Create draft</button>
        </form>
      )}

      {apps.isLoading && <Spinner />}
      <ErrorBox error={apps.error} />
      {apps.data?.length === 0 && <Empty title="No applications yet">Start one to upload documents and run a self-check.</Empty>}
      <ul className="space-y-3">
        {(apps.data || []).map((a) => (
          <li key={a.id}>
            <Link to={`/institution/applications/${a.id}`} className="panel flex flex-wrap items-center justify-between gap-3 p-4 hover:border-ruleDark">
              <div>
                <p className="font-medium">{TYPE_LABEL[a.type]}, AY {a.academic_year}</p>
                <p className="text-sm text-ink-soft">{a.ref_no}, intake {a.requested_intake}</p>
              </div>
              <span className="text-sm">{a.decision ? DECISION_LABEL[a.decision] : STATUS_LABEL[a.status]}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
