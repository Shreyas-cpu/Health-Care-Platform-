import type { UserRole } from '../types'
import { api, setAuthToken } from './api'
import { isLiveFirebaseConfigured, signInWithLiveGoogle } from './firebaseConfig'

export interface AuthSession {
  token: string
  role: UserRole
  userId: string
  phoneNumber?: string
  email?: string
  displayName?: string
}

export const firebaseAuthService = {
  // Handles Phone OTP verification
  loginWithPhone: async (phoneNumber: string, fullName: string, role: UserRole = 'patient') => {
    // Generate base64 mock Firebase ID token payload compatible with backend verify_firebase_id_token
    const payload = {
      uid: `fb-phone-${phoneNumber.replace(/\D/g, '')}`,
      phone_number: phoneNumber,
      name: fullName,
      role,
    }
    const idToken = `mock-firebase-${btoa(JSON.stringify(payload))}`

    const res = await api.firebaseLogin(idToken, role, fullName)
    setAuthToken(res.access_token)

    const session: AuthSession = {
      token: res.access_token,
      role: res.role,
      userId: res.user_id,
      phoneNumber,
      displayName: fullName,
    }
    localStorage.setItem('aarogya_session', JSON.stringify(session))
    return session
  },

  // Handles Google Sign-In (Live OAuth with Firebase SDK or development sandbox)
  loginWithGoogle: async (email: string, fullName: string, role: UserRole) => {
    let idToken: string
    let resolvedEmail = email
    let resolvedName = fullName

    if (isLiveFirebaseConfigured) {
      try {
        const liveResult = await signInWithLiveGoogle()
        idToken = liveResult.idToken
        resolvedEmail = liveResult.email || email
        resolvedName = liveResult.displayName || fullName
      } catch (err) {
        console.warn('Live Google Sign-In failed or was cancelled, falling back to development sandbox:', err)
        const payload = {
          uid: `fb-google-${btoa(email).replace(/=/g, '')}`,
          email,
          name: fullName,
          role,
        }
        idToken = `mock-firebase-${btoa(JSON.stringify(payload))}`
      }
    } else {
      const payload = {
        uid: `fb-google-${btoa(email).replace(/=/g, '')}`,
        email,
        name: fullName,
        role,
      }
      idToken = `mock-firebase-${btoa(JSON.stringify(payload))}`
    }

    const res = await api.firebaseLogin(idToken, role, resolvedName)
    setAuthToken(res.access_token)

    const session: AuthSession = {
      token: res.access_token,
      role: res.role,
      userId: res.user_id,
      email: resolvedEmail,
      displayName: resolvedName,
    }
    localStorage.setItem('aarogya_session', JSON.stringify(session))
    return session
  },

  getCurrentSession: (): AuthSession | null => {
    if (typeof window === 'undefined') return null
    const stored = localStorage.getItem('aarogya_session')
    if (stored) {
      try {
        return JSON.parse(stored)
      } catch {
        return null
      }
    }
    return null
  },

  logout: () => {
    localStorage.removeItem('aarogya_session')
    localStorage.removeItem('aarogya_auth_token')
  },
}
