import React, { useState } from 'react'
import {
  Activity,
  LogOut,
  Settings,
  ShieldCheck,
  Stethoscope,
  Pill,
  User,
  Smartphone,
} from 'lucide-react'
import type { UserRole } from '../../types'
import { getApiBaseUrl, setApiBaseUrl } from '../../services/api'
import type { AuthSession } from '../../services/firebase'

interface HeaderProps {
  currentRole: UserRole
  onSelectRole: (role: UserRole) => void
  session: AuthSession | null
  onLogout: () => void
  onOpenLogin: () => void
}

export const Header: React.FC<HeaderProps> = ({
  currentRole,
  onSelectRole,
  session,
  onLogout,
  onOpenLogin,
}) => {
  const [showConfig, setShowConfig] = useState(false)
  const [apiUrl, setApiUrl] = useState(getApiBaseUrl())

  const handleSaveApiUrl = () => {
    setApiBaseUrl(apiUrl)
    setShowConfig(false)
    window.location.reload()
  }

  const roleMeta: Record<UserRole, { label: string; icon: React.ReactNode; color: string }> = {
    patient: {
      label: 'Patient Portal',
      icon: <User className="w-4 h-4" />,
      color: 'bg-emerald-600 text-white',
    },
    doctor: {
      label: 'Doctor Portal',
      icon: <Stethoscope className="w-4 h-4" />,
      color: 'bg-blue-600 text-white',
    },
    chemist: {
      label: 'Chemist / Druggist',
      icon: <Pill className="w-4 h-4" />,
      color: 'bg-amber-600 text-white',
    },
    super_admin: {
      label: 'Super Admin Ops',
      icon: <ShieldCheck className="w-4 h-4" />,
      color: 'bg-purple-600 text-white',
    },
  }

  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-slate-200 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center text-white shadow-md">
              <Activity className="w-6 h-6" />
            </div>
            <div>
              <span className="text-xl font-bold tracking-tight text-slate-900">
                Aarogya<span className="text-emerald-600">Care</span>
              </span>
              <span className="hidden sm:inline-block ml-2 text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                Clinic First OPD
              </span>
            </div>
          </div>

          {/* Role Switcher Pills */}
          <div className="hidden md:flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200">
            {(['patient', 'doctor', 'chemist', 'super_admin'] as UserRole[]).map((r) => {
              const active = currentRole === r
              return (
                <button
                  key={r}
                  onClick={() => onSelectRole(r)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    active
                      ? `${roleMeta[r].color} shadow-xs`
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
                  }`}
                >
                  {roleMeta[r].icon}
                  {roleMeta[r].label}
                </button>
              )
            })}
          </div>

          {/* Right Controls */}
          <div className="flex items-center gap-2">
            {/* Network / Android Settings button */}
            <button
              onClick={() => setShowConfig(!showConfig)}
              title="Configure API Endpoint (Android Emulator 10.0.2.2 or LAN IP)"
              className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition"
            >
              <Settings className="w-5 h-5" />
            </button>

            {session ? (
              <div className="flex items-center gap-2">
                <div className="hidden sm:block text-right">
                  <div className="text-xs font-semibold text-slate-900">
                    {session.displayName || 'Authenticated User'}
                  </div>
                  <div className="text-[10px] text-slate-500 capitalize">
                    {session.role.replace('_', ' ')}
                  </div>
                </div>
                <button
                  onClick={onLogout}
                  title="Logout"
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 rounded-lg border border-red-200 transition"
                >
                  <LogOut className="w-4 h-4" />
                  <span className="hidden sm:inline">Logout</span>
                </button>
              </div>
            ) : (
              <button
                onClick={onOpenLogin}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm transition"
              >
                <Smartphone className="w-4 h-4" />
                Firebase Login
              </button>
            )}
          </div>
        </div>

        {/* Mobile Role Switcher Bar */}
        <div className="md:hidden flex items-center justify-between overflow-x-auto py-2 border-t border-slate-100 gap-1 scrollbar-none">
          {(['patient', 'doctor', 'chemist', 'super_admin'] as UserRole[]).map((r) => {
            const active = currentRole === r
            return (
              <button
                key={r}
                onClick={() => onSelectRole(r)}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium whitespace-nowrap ${
                  active ? roleMeta[r].color : 'text-slate-600 bg-slate-100'
                }`}
              >
                {roleMeta[r].icon}
                {r === 'super_admin' ? 'Admin' : r.charAt(0).toUpperCase() + r.slice(1)}
              </button>
            )
          })}
        </div>
      </div>

      {/* Network Configuration Modal */}
      {showConfig && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 border border-slate-200">
            <h3 className="text-lg font-bold text-slate-900 mb-1 flex items-center gap-2">
              <Settings className="w-5 h-5 text-emerald-600" />
              API Server Configuration
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Configure backend base URL. Use <code>http://10.0.2.2:8000/api/v1</code> when testing
              inside the <strong>Android Studio Emulator</strong>, or your LAN IP for physical
              devices.
            </p>

            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Backend API Base URL
            </label>
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-hidden mb-4"
              placeholder="http://localhost:8000/api/v1"
            />

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowConfig(false)}
                className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveApiUrl}
                className="px-4 py-1.5 text-xs text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg font-semibold shadow-xs"
              >
                Save & Apply
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  )
}
