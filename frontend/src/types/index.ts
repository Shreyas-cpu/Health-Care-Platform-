export type UserRole = 'patient' | 'doctor' | 'chemist' | 'super_admin'

export interface User {
  id: string
  phone_number?: string | null
  email?: string | null
  role: UserRole
  firebase_uid?: string | null
  is_active: boolean
}

export interface Clinic {
  id?: string
  doctor_id?: string
  name: string
  address: string
  city: string
  locality: string
  pincode: string
  contact_number: string
  latitude?: number | null
  longitude?: number | null
  google_maps_url?: string
}

export interface Doctor {
  doctor_id: string
  full_name: string
  specialty: string
  years_experience: number
  bio?: string | null
  gender?: string | null
  in_person_fee: string | number
  listing_online: boolean
  rating?: number
  review_count?: number
  clinic?: Clinic | null
  latitude?: number | null
  longitude?: number | null
  google_maps_url?: string
}

export type AppointmentStatus =
  | 'requested'
  | 'confirmed'
  | 'rescheduled'
  | 'checked_in'
  | 'in_consultation'
  | 'completed'
  | 'cancelled'
  | 'no_show'

export interface Appointment {
  id: string
  patient_id: string
  doctor_id: string
  clinic_id?: string
  doctor_name?: string
  specialty?: string
  clinic_name?: string
  clinic_address?: string
  google_maps_url?: string
  slot_start: string
  slot_end: string
  status: AppointmentStatus
  fee_amount: number | string
  payment_status: string
  notes?: string | null
  prescription_id?: string | null
  reminder_sent?: boolean
}

export interface PrescriptionItem {
  medicine_name: string
  dosage: string
  frequency: string
  duration: string
  instructions?: string
  is_schedule_x?: boolean
}

export interface Prescription {
  id: string
  appointment_id: string
  doctor_id: string
  patient_id: string
  chemist_id?: string | null
  diagnosis: string
  clinical_notes?: string | null
  items: PrescriptionItem[]
  digital_signature: string
  digital_signature_timestamp: string
  dispense_status: 'pending' | 'dispensed'
  dispensed_at?: string | null
  pdf_s3_key?: string | null
}

export interface Chemist {
  id: string
  user_id: string
  pharmacy_name: string
  license_number: string
  address: string
  city: string
  locality: string
  pincode: string
  contact_number: string
  is_active: boolean
  clinic_id?: string | null
}

export interface PatientDocument {
  id: string
  patient_id: string
  doc_type: string
  file_name: string
  file_size_bytes: number
  notes?: string | null
  created_at: string
  s3_key: string
  download_url?: string
}

export interface PlatformTelemetry {
  total_verified_doctors: number
  total_confirmed_bookings: number
  total_completed_consultations: number
  gross_transaction_value: number
  total_registered_chemists: number
  total_patient_documents: number
}

export interface AuditLog {
  id: string
  admin_user_id: string
  target_entity_type: string
  target_entity_id: string
  action: string
  diff?: Record<string, unknown> | null
  reason?: string | null
  created_at: string
}
