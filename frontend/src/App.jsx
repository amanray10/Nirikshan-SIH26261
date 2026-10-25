import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import Login from './pages/Login'
import Queue from './pages/Queue'
import Workspace from './pages/Workspace'
import Decision from './pages/Decision'
import Assistant from './pages/Assistant'
import Network from './pages/Network'
import Evaluation from './pages/Evaluation'
import Admin from './pages/Admin'
import InstitutionHome from './pages/InstitutionHome'
import InstitutionApplication from './pages/InstitutionApplication'

const NAV = {
  officer: [['/queue', 'Scrutiny queue'], ['/national', 'National view'], ['/aph', 'APH assistant'], ['/evaluation', 'Evaluation']],
  admin: [['/queue', 'Scrutiny queue'], ['/national', 'National view'], ['/aph', 'APH assistant'], ['/evaluation', 'Evaluation'], ['/admin', 'Rules and norms']],
  institution: [['/institution', 'My applications'], ['/aph', 'APH assistant']],
}

function Shell({ children }) {
  const { user, institution, logout } = useAuth()
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-rule bg-sheet/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-8 gap-y-2 px-4 py-2.5 sm:px-6">
          <NavLink to="/" className="flex items-center gap-2.5">
            <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden><rect width="32" height="32" rx="6" fill="#1B2340" /><circle cx="16" cy="16" r="9" fill="none" stroke="#F4F6F1" strokeWidth="2.4" /><path d="M11.5 16.5l3 3 6-7" fill="none" stroke="#F4F6F1" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
            <span className="leading-tight">
              <span className="block font-cond text-lg font-bold">Nirikshan</span>
              <span className="block text-xxs text-ink-soft"><span className="font-deva">निरीक्षण</span>, AICTE approval scrutiny</span>
            </span>
          </NavLink>
          <nav className="scroll-thin order-last -mx-1 flex w-full gap-x-5 overflow-x-auto px-1 md:order-none md:w-auto md:flex-1" aria-label="Main">
            {(NAV[user.role] || []).map(([to, label]) => (
              <NavLink key={to} to={to} className={({ isActive }) => `whitespace-nowrap py-1 text-sm ${isActive ? 'font-medium text-ink underline decoration-royal decoration-2 underline-offset-[10px]' : 'text-ink-soft hover:text-ink'}`}>
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm md:ml-0">
            <span className="hidden text-right leading-tight md:block">
              <span className="block font-medium">{user.name || user.email}</span>
              <span className="block text-xs text-ink-soft">{institution ? institution.name : user.role === 'admin' ? 'Administrator' : 'Scrutiny officer'}</span>
            </span>
            <button className="btn-quiet py-1.5" onClick={logout}>Sign out</button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6">{children}</main>
    </div>
  )
}

function Guard({ roles, children }) {
  const { user } = useAuth()
  const loc = useLocation()
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />
  return <Shell>{children}</Shell>
}

function Home() {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return <Navigate to={user.role === 'institution' ? '/institution' : '/queue'} replace />
}

export default function App() {
  const staff = ['officer', 'admin']
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Home />} />
      <Route path="/queue" element={<Guard roles={staff}><Queue /></Guard>} />
      <Route path="/applications/:id" element={<Guard roles={staff}><Workspace /></Guard>} />
      <Route path="/applications/:id/decision" element={<Guard roles={staff}><Decision /></Guard>} />
      <Route path="/national" element={<Guard roles={staff}><Network /></Guard>} />
      <Route path="/evaluation" element={<Guard roles={staff}><Evaluation /></Guard>} />
      <Route path="/admin" element={<Guard roles={['admin']}><Admin /></Guard>} />
      <Route path="/aph" element={<Guard><Assistant /></Guard>} />
      <Route path="/institution" element={<Guard roles={['institution']}><InstitutionHome /></Guard>} />
      <Route path="/institution/applications/:id" element={<Guard roles={['institution']}><InstitutionApplication /></Guard>} />
      <Route path="*" element={<Home />} />
    </Routes>
  )
}
