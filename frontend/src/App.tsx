import { useEffect, useState } from 'react'
import type { UserRole } from './types'
import { firebaseAuthService, type AuthSession } from './services/firebase'
import { Header } from './components/common/Header'
import { AuthModal } from './components/auth/AuthModal'
import { PatientPortal } from './components/patient/PatientPortal'
import { DoctorPortal } from './components/doctor/DoctorPortal'
import { ChemistPortal } from './components/chemist/ChemistPortal'
import { AdminPortal } from './components/admin/AdminPortal'

export function App() {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [currentRole, setCurrentRole] = useState<UserRole>('patient')
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false)

  // Load session on startup
  useEffect(() => {
    const saved = firebaseAuthService.getCurrentSession()
    if (saved) {
      setSession(saved)
      setCurrentRole(saved.role)
    }
  }, [])

  const handleRoleSelect = (role: UserRole) => {
    setCurrentRole(role)
  }

  const handleLogout = () => {
    firebaseAuthService.logout()
    setSession(null)
  }

  const handleAuthSuccess = (newSession: AuthSession) => {
    setSession(newSession)
    setCurrentRole(newSession.role)
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Top Header & Role Switcher */}
      <Header
        currentRole={currentRole}
        onSelectRole={handleRoleSelect}
        session={session}
        onLogout={handleLogout}
        onOpenLogin={() => setIsAuthModalOpen(true)}
      />

      {/* Main Role-Based Content Area */}
      <main className="flex-1">
        {currentRole === 'patient' && (
          <PatientPortal
            session={session}
            onRequireLogin={() => setIsAuthModalOpen(true)}
          />
        )}

        {currentRole === 'doctor' && (
          <DoctorPortal
            session={session}
            onRequireLogin={() => setIsAuthModalOpen(true)}
          />
        )}

        {currentRole === 'chemist' && (
          <ChemistPortal
            session={session}
            onRequireLogin={() => setIsAuthModalOpen(true)}
          />
        )}

        {currentRole === 'super_admin' && (
          <AdminPortal
            session={session}
            onRequireLogin={() => setIsAuthModalOpen(true)}
          />
        )}
      </main>

      {/* Authentication Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        defaultRole={currentRole}
        onClose={() => setIsAuthModalOpen(false)}
        onSuccess={handleAuthSuccess}
      />

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-6 text-center text-xs text-slate-400">
        <div className="max-w-7xl mx-auto px-4">
          <p className="font-semibold text-slate-600">
            AarogyaCare Healthcare Platform — Outpatient Department (OPD) Marketplace
          </p>
          <p className="mt-1">
            Compliant with Drugs & Cosmetics Act, DPDP Act 2023, and IT Act 2000 Electronic Signatures.
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App
