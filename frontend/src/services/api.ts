import type {
  Appointment,
  Chemist,
  Doctor,
  PatientDocument,
  PlatformTelemetry,
  Prescription,
  User,
  UserRole,
} from '../types'

// Automatically detect host: 10.0.2.2 for Android Studio Emulator, localhost for desktop browser
const isAndroidEmulator =
  typeof window !== 'undefined' &&
  window.navigator &&
  /android/i.test(window.navigator.userAgent)

const getStoredBaseUrl = () => {
  if (typeof window !== 'undefined') {
    return (
      localStorage.getItem('aarogya_api_base_url') ||
      (isAndroidEmulator ? 'http://10.0.2.2:8000/api/v1' : 'http://localhost:8000/api/v1')
    )
  }
  return 'http://localhost:8000/api/v1'
}

let API_BASE_URL = getStoredBaseUrl()

export const setApiBaseUrl = (url: string) => {
  API_BASE_URL = url
  localStorage.setItem('aarogya_api_base_url', url)
}

export const getApiBaseUrl = () => API_BASE_URL

export const getAuthToken = () => localStorage.getItem('aarogya_auth_token')
export const setAuthToken = (token: string) => localStorage.setItem('aarogya_auth_token', token)
export const clearAuthToken = () => localStorage.removeItem('aarogya_auth_token')

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken()
  const headers = new Headers(options.headers || {})

  if (!(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    let errorDetail = `Request failed: ${response.status} ${response.statusText}`
    try {
      const errJson = await response.json()
      errorDetail = errJson.detail || errJson.message || errorDetail
    } catch {
      // ignore
    }
    throw new Error(errorDetail)
  }

  return response.json()
}

export const api = {
  // Auth
  firebaseLogin: (idToken: string, role: UserRole = 'patient', fullName?: string) =>
    request<{ access_token: string; role: UserRole; user_id: string; is_new_user: boolean }>(
      '/auth/firebase/login',
      {
        method: 'POST',
        body: JSON.stringify({
          id_token: idToken,
          role,
          full_name: fullName,
          consent_version: 'v1.0',
        }),
      }
    ),

  getMe: () => request<User>('/auth/me'),

  // Doctor & Discovery
  searchDoctors: (params: { specialty?: string; locality?: string; city?: string }) => {
    const query = new URLSearchParams()
    if (params.specialty) query.set('specialty', params.specialty)
    if (params.locality) query.set('locality', params.locality)
    if (params.city) query.set('city', params.city)
    return request<{ items: Doctor[]; total: number }>(`/search/doctors?${query.toString()}`)
  },

  getDoctorProfile: (doctorId: string) => request<Doctor>(`/doctors/${doctorId}`),

  upsertClinic: (clinicData: {
    name: string
    address: string
    city: string
    locality: string
    pincode: string
    contact_number: string
    latitude?: number
    longitude?: number
  }) =>
    request('/doctors/me/clinic', {
      method: 'POST',
      body: JSON.stringify(clinicData),
    }),

  updateAvailability: (availability: {
    day_of_week: number
    start_time: string
    end_time: string
    slot_duration_minutes?: number
  }) =>
    request('/schedules/availability', {
      method: 'POST',
      body: JSON.stringify(availability),
    }),

  getDoctorQueue: () => request<{ queue: Appointment[] }>('/doctor/queue'),

  // Bookings & Patient Portal
  getSlots: (doctorId: string, dateStr: string) =>
    request<{ slots: Array<{ start_time: string; end_time: string; is_available: boolean }> }>(
      `/doctors/${doctorId}/slots?query_date=${dateStr}&mode=in_person`
    ),

  reserveSlot: (data: {
    doctor_id: string
    slot_start: string
    slot_end: string
    patient_name: string
    notes?: string
  }) =>
    request<{ appointment_id: string; status: string }>('/bookings/reserve', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  confirmAppointment: (appointmentId: string) =>
    request(`/appointments/${appointmentId}/confirm`, {
      method: 'POST',
    }),

  cancelAppointment: (appointmentId: string, reason: string) =>
    request(`/appointments/${appointmentId}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  getAppointmentHistory: () =>
    request<{ appointments: Appointment[] }>('/patients/me/appointments/history'),

  // Health Document Vault
  uploadPatientDocument: (file: File, docType: string, notes?: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('doc_type', docType)
    if (notes) formData.append('notes', notes)
    return request<PatientDocument>('/patients/me/documents', {
      method: 'POST',
      body: formData,
    })
  },

  getPatientDocuments: () =>
    request<{ documents: PatientDocument[]; prescriptions: Prescription[] }>(
      '/patients/me/documents'
    ),

  // Prescriptions & Digital Signatures
  createPrescription: (prescription: {
    appointment_id: string
    diagnosis: string
    clinical_notes?: string
    chemist_id?: string | null
    items: Array<{
      medicine_name: string
      dosage: string
      frequency: string
      duration: string
      instructions?: string
      is_schedule_x?: boolean
    }>
  }) =>
    request<Prescription>('/prescriptions', {
      method: 'POST',
      body: JSON.stringify(prescription),
    }),

  verifyPrescriptionSignature: (prescriptionId: string) =>
    request<{ valid: boolean; doctor_medical_reg_number: string; timestamp: string; hash: string }>(
      `/prescriptions/${prescriptionId}/verify`
    ),

  // Chemist / Druggist
  registerChemist: (data: {
    pharmacy_name: string
    license_number: string
    address: string
    city: string
    locality: string
    pincode: string
    contact_number: string
    clinic_id?: string | null
  }) =>
    request<Chemist>('/chemists/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listChemists: () => request<{ items: Chemist[] }>('/chemists'),

  getChemistPrescriptions: () =>
    request<{ prescriptions: Prescription[] }>('/chemist/prescriptions'),

  dispensePrescription: (prescriptionId: string) =>
    request<{ success: boolean; message: string; dispensed_at: string }>(
      `/chemist/prescriptions/${prescriptionId}/dispense`,
      {
        method: 'POST',
      }
    ),

  // Super Admin & Oversight
  getAdminTelemetry: () => request<PlatformTelemetry>('/admin/dashboard/telemetry'),

  listChemistsForAdmin: () => request<{ chemists: Chemist[] }>('/admin/moderation/chemists'),

  updateChemistStatus: (chemistId: string, action: 'activate' | 'suspend', reasonText: string) =>
    request(`/admin/moderation/chemists/${chemistId}/status`, {
      method: 'POST',
      body: JSON.stringify({ action, reason_text: reasonText }),
    }),

  dispatchReminders: () =>
    request<{ dispatched_count: number; timestamp: string }>(
      '/admin/dashboard/dispatch-reminders',
      {
        method: 'POST',
      }
    ),
}
