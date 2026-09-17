import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.aarogyacare.health',
  appName: 'AarogyaCare Healthcare',
  webDir: 'dist',
  server: {
    androidScheme: 'http',
    cleartext: true, // Allows dev HTTP connections to local backend (10.0.2.2 / LAN IP)
  },
  plugins: {
    GoogleAuth: {
      scopes: ['profile', 'email'],
      serverClientId: '364667500884-0d873p88nnefqdtj15pnqpplvri4i8cj.apps.googleusercontent.com',
      forceCodeForRefreshToken: true,
    },
  },
}

export default config
