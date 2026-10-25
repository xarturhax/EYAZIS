import { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { FileText, GitBranch, Users, Download, HelpCircle, X, Gamepad2 } from 'lucide-react'
import { LanguageProvider, useLanguage } from './i18n/LanguageContext'
import DocumentsPage from './pages/DocumentsPage'
import SyntaxPage from './pages/SyntaxPage'
import RolesPage from './pages/RolesPage'
import ExportPage from './pages/ExportPage'
import QuizPage from './pages/QuizPage'

function HelpModal({ onClose }: { onClose: () => void }) {
  const { t } = useLanguage()
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-2xl max-w-xl w-full mx-4 max-h-[85vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-base font-bold text-gray-800">{t.helpTitle}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-4 space-y-5">
          {t.helpSections.map(section => (
            <div key={section.title}>
              <h3 className="text-sm font-semibold text-indigo-700 mb-1">{section.title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{section.body}</p>
            </div>
          ))}
        </div>
        <div className="px-6 py-3 border-t border-gray-200 flex justify-end">
          <button
            onClick={onClose}
            className="bg-indigo-600 text-white rounded px-4 py-1.5 text-sm font-medium hover:bg-indigo-700"
          >
            {t.helpClose}
          </button>
        </div>
      </div>
    </div>
  )
}

function AppLayout() {
  const { t, toggleLang } = useLanguage()
  const [helpOpen, setHelpOpen] = useState(false)

  const NAV = [
    { to: '/', label: t.navDocuments, icon: FileText },
    { to: '/syntax', label: t.navSyntax, icon: GitBranch },
    { to: '/roles', label: t.navRoles, icon: Users },
    { to: '/export', label: t.navExport, icon: Download },
    { to: '/quiz', label: t.navQuiz, icon: Gamepad2 },
  ]

  return (
    <div className="flex h-screen bg-gray-50">
      {helpOpen && <HelpModal onClose={() => setHelpOpen(false)} />}

      {/* Sidebar */}
      <aside className="w-52 bg-white border-r border-gray-200 flex flex-col shadow-sm shrink-0">
        <div className="px-4 py-5 border-b border-gray-200">
          <h1 className="text-sm font-bold text-gray-800 leading-tight">{t.appTitle}</h1>
          <p className="text-xs text-gray-500 mt-0.5">{t.appSubtitle}</p>
        </div>
        <nav className="flex-1 px-2 py-3 space-y-0.5">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700 font-medium'
                    : 'text-gray-600 hover:bg-gray-100'
                }`
              }
            >
              <Icon size={15} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-2 py-3 border-t border-gray-200 space-y-1">
          <button
            onClick={() => setHelpOpen(true)}
            className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-gray-600 hover:bg-gray-100 w-full transition-colors"
          >
            <HelpCircle size={15} />
            {t.helpBtn}
          </button>
          <button
            onClick={toggleLang}
            className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-gray-600 hover:bg-gray-100 w-full transition-colors"
          >
            <span className="text-xs font-bold bg-gray-100 text-gray-600 rounded px-1.5 py-0.5">
              {t.langToggle}
            </span>
            <span>Language</span>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<DocumentsPage />} />
          <Route path="/syntax" element={<SyntaxPage />} />
          <Route path="/roles" element={<RolesPage />} />
          <Route path="/export" element={<ExportPage />} />
          <Route path="/quiz" element={<QuizPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <LanguageProvider>
        <AppLayout />
      </LanguageProvider>
    </BrowserRouter>
  )
}
