import { initializeApp, getApps, type FirebaseApp } from 'firebase/app'
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signInWithCredential,
  RecaptchaVerifier,
  signInWithPhoneNumber,
  type Auth,
  type ConfirmationResult,
} from 'firebase/auth'
import { Capacitor } from '@capacitor/core'
import { GoogleAuth } from '@codetrix-studio/capacitor-google-auth'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || 'aarogyacare-healthcare',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || '',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
}

export const isLiveFirebaseConfigured = Boolean(
  firebaseConfig.apiKey && firebaseConfig.apiKey.length > 10
)

let app: FirebaseApp | null = null
let auth: Auth | null = null
let googleProvider: GoogleAuthProvider | null = null

if (isLiveFirebaseConfigured) {
  try {
    app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0]
    auth = getAuth(app)
    googleProvider = new GoogleAuthProvider()
  } catch (err) {
    console.warn('Firebase initialization warning:', err)
  }
}

export { app, auth, googleProvider }

export async function sendLivePhoneOtp(
  phoneNumber: string,
  containerId: string = 'recaptcha-container'
): Promise<ConfirmationResult> {
  if (!auth) {
    throw new Error('Firebase Auth is not initialized with live credentials.')
  }
  const appVerifier = new RecaptchaVerifier(auth, containerId, {
    size: 'invisible',
  })
  return signInWithPhoneNumber(auth, phoneNumber, appVerifier)
}

const SERVER_CLIENT_ID = '364667500884-0d873p88nnefqdtj15pnqpplvri4i8cj.apps.googleusercontent.com'

let isNativeGoogleAuthReady = false

export async function initNativeGoogleAuth(): Promise<void> {
  if (isNativeGoogleAuthReady) return
  try {
    await GoogleAuth.initialize({
      clientId: SERVER_CLIENT_ID,
      scopes: ['profile', 'email'],
      grantOfflineAccess: true,
    })
    isNativeGoogleAuthReady = true
  } catch (err) {
    console.warn('Native GoogleAuth.initialize notice:', err)
  }
}

export async function signInWithNativeGoogle(): Promise<{ idToken: string; email: string; displayName: string }> {
  await initNativeGoogleAuth()
  const googleUser = await GoogleAuth.signIn()

  const rawIdToken = googleUser.authentication?.idToken
  if (!rawIdToken) {
    throw new Error('Google Sign-In completed on device, but no ID token was returned.')
  }

  // If Firebase Auth instance is active in the WebView, link Google credentials with Firebase
  if (auth) {
    try {
      const credential = GoogleAuthProvider.credential(rawIdToken)
      const userCredential = await signInWithCredential(auth, credential)
      const firebaseIdToken = await userCredential.user.getIdToken()
      return {
        idToken: firebaseIdToken,
        email: userCredential.user.email || googleUser.email || '',
        displayName: userCredential.user.displayName || googleUser.name || '',
      }
    } catch (fbErr) {
      console.warn('Direct Firebase credential exchange fallback; using Google OAuth ID token directly:', fbErr)
    }
  }

  return {
    idToken: rawIdToken,
    email: googleUser.email || '',
    displayName: googleUser.name || '',
  }
}

export async function signInWithLiveGoogle(): Promise<{ idToken: string; email: string; displayName: string }> {
  // Check if running on Android native platform or Capacitor native environment
  if (Capacitor.isNativePlatform() || (typeof window !== 'undefined' && (window as unknown as { Capacitor?: { isNativePlatform?: () => boolean } }).Capacitor?.isNativePlatform?.())) {
    return signInWithNativeGoogle()
  }

  // Web Browser Fallback: standard Firebase popup
  if (!auth || !googleProvider) {
    throw new Error('Firebase Auth is not initialized with live credentials.')
  }

  const timeoutPromise = new Promise<never>((_, reject) => {
    setTimeout(() => reject(new Error('Google Sign-In timed out.')), 15000)
  })

  const result = await Promise.race([signInWithPopup(auth, googleProvider), timeoutPromise])
  const idToken = await result.user.getIdToken()
  return {
    idToken,
    email: result.user.email || '',
    displayName: result.user.displayName || '',
  }
}
