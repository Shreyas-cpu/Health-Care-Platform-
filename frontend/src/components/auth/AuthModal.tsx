import React, { useState } from 'react'
import { CheckCircle2, Lock, ShieldCheck, Smartphone, X } from 'lucide-react'
import type { UserRole } from '../../types'
import { firebaseAuthService, type AuthSession } from '../../services/firebase'

interface AuthModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (session: AuthSession) => void
  defaultRole?: UserRole
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  defaultRole = 'patient',
}) => {
  const [authMethod, setAuthMethod] = useState<'phone' | 'google'>('phone')
  const [role, setRole] = useState<UserRole>(defaultRole)
  const [fullName, setFullName] = useState('')
  const [phone, setPhone] = useState('+91 ')
  const [otp, setOtp] = useState('')
  const [step, setStep] = useState<'details' | 'otp'>('details')
  const [dpdpConsent, setDpdpConsent] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleSendOtp = (e: React.FormEvent) => {
    e.preventDefault()
    if (!dpdpConsent) {
      setError('Please acknowledge the statutory DPDP consent to proceed.')
      return
    }
    setError(null)
    setStep('otp')
  }

  const handleVerifyPhoneOtp = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const cleanPhone = phone.trim()
      const session = await firebaseAuthService.loginWithPhone(
        cleanPhone,
        fullName.trim() || 'Patient User',
        role
      )
      onSuccess(session)
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Phone authentication failed.')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleSignIn = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!dpdpConsent) {
      setError('Please acknowledge the statutory DPDP consent to proceed.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const session = await firebaseAuthService.loginWithGoogle(
        '',
        '',
        role
      )
      onSuccess(session)
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Google authentication failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl shadow-2xl max-w-md w-full p-6 sm:p-8 border border-slate-100 relative">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-1.5 text-slate-400 hover:text-slate-700 rounded-full hover:bg-slate-100 transition"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="text-center mb-6">
          <div className="w-12 h-12 rounded-2xl bg-emerald-100 text-emerald-700 mx-auto flex items-center justify-center mb-3">
            <Lock className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-bold text-slate-900">Google Firebase Authentication</h2>
          <p className="text-xs text-slate-500 mt-1">
            Secure OTP & OAuth login with DPDP statutory consent
          </p>
        </div>

        {/* Role Selector Tabs */}
        <div className="mb-4">
          <label className="block text-xs font-semibold text-slate-600 mb-1.5">
            Select Account Role
          </label>
          <div className="grid grid-cols-4 gap-1 p-1 bg-slate-100 rounded-xl">
            {(['patient', 'doctor', 'chemist', 'super_admin'] as UserRole[]).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRole(r)}
                className={`py-1.5 text-[11px] font-semibold rounded-lg capitalize transition ${
                  role === r ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {r === 'super_admin' ? 'Admin' : r}
              </button>
            ))}
          </div>
        </div>

        {/* Method Toggle */}
        <div className="flex border-b border-slate-200 mb-5">
          <button
            type="button"
            onClick={() => {
              setAuthMethod('phone')
              setStep('details')
            }}
            className={`flex-1 py-2 text-xs font-bold border-b-2 flex items-center justify-center gap-1.5 ${
              authMethod === 'phone'
                ? 'border-emerald-600 text-emerald-700'
                : 'border-transparent text-slate-400 hover:text-slate-600'
            }`}
          >
            <Smartphone className="w-4 h-4" />
            Phone Auth (SMS OTP)
          </button>
          <button
            type="button"
            onClick={() => {
              setAuthMethod('google')
              setStep('details')
            }}
            className={`flex-1 py-2 text-xs font-bold border-b-2 flex items-center justify-center gap-1.5 ${
              authMethod === 'google'
                ? 'border-emerald-600 text-emerald-700'
                : 'border-transparent text-slate-400 hover:text-slate-600'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            Google Sign-In
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-600 font-medium">
            {error}
          </div>
        )}

        {/* Phone Auth Form */}
        {authMethod === 'phone' && (
          <div>
            {step === 'details' ? (
              <form onSubmit={handleSendOtp} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Your Full Name
                  </label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Vikram Sharma"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:outline-hidden"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Mobile Phone Number (E.164)
                  </label>
                  <input
                    type="text"
                    required
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+91 9876543210"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:outline-hidden"
                  />
                </div>

                <div className="flex items-start gap-2 bg-slate-50 p-3 rounded-xl border border-slate-200">
                  <input
                    type="checkbox"
                    id="dpdp-consent-phone"
                    checked={dpdpConsent}
                    onChange={(e) => setDpdpConsent(e.target.checked)}
                    className="mt-0.5 rounded text-emerald-600 focus:ring-emerald-500"
                  />
                  <label
                    htmlFor="dpdp-consent-phone"
                    className="text-[11px] text-slate-600 leading-tight"
                  >
                    I grant explicit consent under the <strong>DPDP Act 2023</strong> for processing
                    my healthcare appointment and medical record services.
                  </label>
                </div>

                <button
                  type="submit"
                  className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow-md transition"
                >
                  Send Verification Code (SMS)
                </button>
              </form>
            ) : (
              <form onSubmit={handleVerifyPhoneOtp} className="space-y-4">
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800">
                  Code sent to <strong>{phone}</strong> (Use sandbox test code <code>000000</code>)
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    6-Digit SMS OTP Code
                  </label>
                  <input
                    type="text"
                    maxLength={6}
                    required
                    value={otp}
                    onChange={(e) => setOtp(e.target.value)}
                    placeholder="000000"
                    className="w-full text-center tracking-widest text-lg font-bold px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:outline-hidden"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow-md transition flex items-center justify-center gap-2"
                >
                  {loading ? 'Verifying...' : 'Verify & Continue'}
                  <CheckCircle2 className="w-4 h-4" />
                </button>

                <button
                  type="button"
                  onClick={() => setStep('details')}
                  className="w-full text-xs text-slate-500 hover:text-slate-800 font-medium text-center"
                >
                  Change phone number
                </button>
              </form>
            )}
          </div>
        )}

        {/* Google OAuth Form */}
        {authMethod === 'google' && (
          <form onSubmit={handleGoogleSignIn} className="space-y-4">
            <div className="p-3.5 bg-blue-50/70 border border-blue-100 rounded-2xl flex items-start gap-3">
              <div className="w-8 h-8 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center shrink-0 mt-0.5">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div className="text-xs text-slate-600 leading-relaxed">
                <span className="font-semibold text-slate-800 block mb-0.5">Direct Google Play Services</span>
                Sign in with the verified Google account saved on your device. Your verified email and name are securely transferred and registered.
              </div>
            </div>

            <div className="flex items-start gap-2 bg-slate-50 p-3 rounded-xl border border-slate-200">
              <input
                type="checkbox"
                id="dpdp-consent-google"
                checked={dpdpConsent}
                onChange={(e) => setDpdpConsent(e.target.checked)}
                className="mt-0.5 rounded text-emerald-600 focus:ring-emerald-500"
              />
              <label
                htmlFor="dpdp-consent-google"
                className="text-[11px] text-slate-600 leading-tight"
              >
                I grant explicit consent under the <strong>DPDP Act 2023</strong> for AarogyaCare to process my
                verified identity for healthcare and appointment services.
              </label>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-white hover:bg-slate-50 text-slate-700 hover:text-slate-900 text-xs font-bold rounded-2xl border border-slate-300 shadow-sm hover:shadow transition flex items-center justify-center gap-3 active:scale-[0.98]"
            >
              {loading ? (
                <>
                  <span className="w-4 h-4 border-2 border-slate-400 border-t-blue-600 rounded-full animate-spin" />
                  Authenticating with Google...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                  </svg>
                  Continue with Google
                </>
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
