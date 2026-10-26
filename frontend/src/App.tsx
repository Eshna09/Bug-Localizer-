import { Routes, Route, NavLink } from 'react-router-dom'
import { Bug, FlaskConical } from 'lucide-react'
import clsx from 'clsx'
import BugAnalysisPage from './pages/BugAnalysis'
import HistoryPage from './pages/History'
import RepositoryDetailsPage from './pages/RepositoryDetails'
import EvaluationPage from './pages/Evaluation'

// History route kept for backward compat (direct URL access), removed from nav
const navItems = [
  { to: '/',           label: 'Bug Analysis', icon: Bug },
  { to: '/evaluation', label: 'Evaluation',   icon: FlaskConical },
]

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Top nav */}
      <header className="border-b border-gray-800 bg-gray-950/95 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-8">
          <div className="flex items-center gap-2 font-semibold text-white">
            <Bug className="text-brand-500" size={20} />
            <span>AI Bug Localizer</span>
          </div>
          <nav className="flex items-center gap-1">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors',
                    isActive
                      ? 'bg-brand-500/20 text-brand-300'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
                  )
                }
              >
                <Icon size={15} />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto text-xs text-gray-600 font-mono">v1.0.0</div>
        </div>
      </header>

      {/* Page content */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
        <Routes>
          <Route path="/" element={<BugAnalysisPage />} />
          <Route path="/evaluation" element={<EvaluationPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/repository/:analysisId" element={<RepositoryDetailsPage />} />
        </Routes>
      </main>
    </div>
  )
}
