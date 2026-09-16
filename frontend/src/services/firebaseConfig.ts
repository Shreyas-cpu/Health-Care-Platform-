import { initializeApp, getApps, type FirebaseApp } from 'firebase/app'
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  RecaptchaVerifier,
  signInWithPhoneNumber,
  type Auth,
  type ConfirmationResult,
} from 'firebase/auth'

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

export async function signInWithLiveGoogle(): Promise<{ idToken: string; email: string; displayName: string }> {
  if (!auth || !googleProvider) {
    throw new Error('Firebase Auth is not initialized with live credentials.')
  }
  const result = await signInWithPopup(auth, googleProvider)
  const idToken = await result.user.getIdToken()
  return {
    idToken,
    email: result.user.email || '',
    displayName: result.user.displayName || '',
  }
}
