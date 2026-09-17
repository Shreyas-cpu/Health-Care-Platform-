import React, { useEffect, useState } from 'react'
import {
  Calendar,
  CheckCircle2,
  Clock,
  Compass,
  Download,
  FileText,
  FolderLock,
  MapPin,
  Search,
  Sparkles,
  Upload,
  XCircle,
} from 'lucide-react'
import type { Appointment, Doctor, PatientDocument, Prescription, PrescriptionItem } from '../../types'
import { api } from '../../services/api'
import type { AuthSession } from '../../services/firebase'

interface PatientPortalProps {
  session: AuthSession | null
  onRequireLogin: () => void
}

export const PatientPortal: React.FC<PatientPortalProps> = ({ session, onRequireLogin }) => {
  const [activeTab, setActiveTab] = useState<'find' | 'appointments' | 'vault'>('find')

  // Search & Discovery state
  const [doctors, setDoctors] = useState<Doctor[]>([])
  const [loadingDoctors, setLoadingDoctors] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSpecialty, setSelectedSpecialty] = useState<string>('All')
  const [selectedCity, setSelectedCity] = useState<string>('Chhatrapati Sambhaji Nagar')

  const cities = [
    'Chhatrapati Sambhaji Nagar',
    'All Cities',
    'Mumbai',
    'Bengaluru',
  ]

  // Booking Modal state
  const [selectedDoctor, setSelectedDoctor] = useState<Doctor | null>(null)
  const [bookingDate, setBookingDate] = useState<string>(new Date().toISOString().split('T')[0])
  const [slots, setSlots] = useState<Array<{ start_time: string; end_time: string; is_available: boolean }>>([])
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null)
  const [bookingNotes, setBookingNotes] = useState('')
  const [bookingSubmitting, setBookingSubmitting] = useState(false)
  const [bookingSuccess, setBookingSuccess] = useState<string | null>(null)

  // Appointments state
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [loadingAppointments, setLoadingAppointments] = useState(false)

  // Vault state
  const [vaultDocs, setVaultDocs] = useState<PatientDocument[]>([])
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([])
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [docType, setDocType] = useState('lab_report')
  const [docNotes, setDocNotes] = useState('')
  const [uploading, setUploading] = useState(false)

  const specialties = [
    'All',
    'General Physician',
    'Dermatology',
    'Cardiology',
    'Pediatrics',
    'Orthopedics',
    'Dentistry',
    'ENT',
    'Ophthalmology',
    'Neurology',
    'Gynecology',
  ]

  // Load doctors on mount and filter changes
  useEffect(() => {
    loadDoctors()
  }, [selectedSpecialty, selectedCity])

  // Load appointments and vault when tab switches
  useEffect(() => {
    if (activeTab === 'appointments' && session) {
      loadAppointments()
    } else if (activeTab === 'vault' && session) {
      loadVault()
    }
  }, [activeTab, session])

  const loadDoctors = async () => {
    setLoadingDoctors(true)
    try {
      const params: { specialty?: string; city?: string } = {}
      if (selectedSpecialty !== 'All') params.specialty = selectedSpecialty
      if (selectedCity !== 'All Cities') params.city = selectedCity
      const res = await api.searchDoctors(params)
      setDoctors(res.items || [])
    } catch {
      setDoctors([])
    } finally {
      setLoadingDoctors(false)
    }
  }

  const loadAppointments = async () => {
    setLoadingAppointments(true)
    try {
      const res = await api.getAppointmentHistory()
      setAppointments(res.appointments || [])
    } catch {
      setAppointments([])
    } finally {
      setLoadingAppointments(false)
    }
  }

  const loadVault = async () => {
    try {
      const res = await api.getPatientDocuments()
      setVaultDocs(res.documents || [])
      setPrescriptions(res.prescriptions || [])
    } catch {
      setVaultDocs([])
      setPrescriptions([])
    }
  }

  const handleOpenBooking = async (doctor: Doctor) => {
    if (!session) {
      onRequireLogin()
      return
    }
    setSelectedDoctor(doctor)
    setSelectedSlot(null)
    setBookingSuccess(null)
    loadSlots(doctor.doctor_id, bookingDate)
  }

  const loadSlots = async (doctorId: string, dateStr: string) => {
    try {
      const res = await api.getSlots(doctorId, dateStr)
      setSlots(res.slots || [])
    } catch {
      setSlots([])
    }
  }

  const handleConfirmBooking = async () => {
    if (!selectedDoctor || !selectedSlot) return
    setBookingSubmitting(true)
    try {
      const matchingSlot = slots.find(
        (s) => s.start_time.slice(11, 16) === selectedSlot || s.start_time === selectedSlot
      )
      const slotStart = matchingSlot ? matchingSlot.start_time : `${bookingDate}T${selectedSlot}:00Z`
      const slotEnd = matchingSlot ? matchingSlot.end_time : `${bookingDate}T${selectedSlot}:15Z`
      const res = await api.reserveSlot({
        doctor_id: selectedDoctor.doctor_id,
        clinic_id: selectedDoctor.clinic?.id,
        slot_start: slotStart,
        slot_end: slotEnd,
        patient_name: session?.displayName || 'Patient',
        notes: bookingNotes,
      })
      setBookingSuccess(
        `Appointment reserved! (ID: ${res.appointment_id.slice(0, 8)}). Pay ₹${selectedDoctor.in_person_fee} in-person at the clinic.`
      )
      setTimeout(() => {
        setSelectedDoctor(null)
        setActiveTab('appointments')
      }, 2000)
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Booking failed')
    } finally {
      setBookingSubmitting(false)
    }
  }

  const handleCancelBooking = async (appointmentId: string) => {
    if (!confirm('Are you sure you want to cancel this appointment?')) return
    try {
      await api.cancelAppointment(appointmentId, 'Patient requested cancellation')
      loadAppointments()
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Cancellation failed')
    }
  }

  const handleUploadDocument = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!uploadFile) return
    setUploading(true)
    try {
      await api.uploadPatientDocument(uploadFile, docType, docNotes)
      setUploadFile(null)
      setDocNotes('')
      loadVault()
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const filteredDoctors = doctors.filter((doc) => {
    const q = searchQuery.toLowerCase()
    return (
      doc.full_name.toLowerCase().includes(q) ||
      doc.specialty.toLowerCase().includes(q) ||
      (doc.clinic?.name && doc.clinic.name.toLowerCase().includes(q)) ||
      (doc.clinic?.locality && doc.clinic.locality.toLowerCase().includes(q)) ||
      (doc.clinic?.city && doc.clinic.city.toLowerCase().includes(q))
    )
  })

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Tab Switcher */}
      <div className="flex border-b border-slate-200 mb-6 gap-2 sm:gap-6 overflow-x-auto">
        <button
          onClick={() => setActiveTab('find')}
          className={`pb-3 text-xs sm:text-sm font-bold flex items-center gap-2 border-b-2 transition whitespace-nowrap ${
            activeTab === 'find'
              ? 'border-emerald-600 text-emerald-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Compass className="w-4 h-4" />
          Find Doctors & Clinics
        </button>

        <button
          onClick={() => {
            if (!session) onRequireLogin()
            else setActiveTab('appointments')
          }}
          className={`pb-3 text-xs sm:text-sm font-bold flex items-center gap-2 border-b-2 transition whitespace-nowrap ${
            activeTab === 'appointments'
              ? 'border-emerald-600 text-emerald-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Calendar className="w-4 h-4" />
          My Appointments
        </button>

        <button
          onClick={() => {
            if (!session) onRequireLogin()
            else setActiveTab('vault')
          }}
          className={`pb-3 text-xs sm:text-sm font-bold flex items-center gap-2 border-b-2 transition whitespace-nowrap ${
            activeTab === 'vault'
              ? 'border-emerald-600 text-emerald-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <FolderLock className="w-4 h-4" />
          Health Document Vault
        </button>
      </div>

      {/* TAB 1: FIND DOCTORS */}
      {activeTab === 'find' && (
        <div className="space-y-6">
          {/* Search Banner & Filters */}
          <div className="bg-white p-4 sm:p-6 rounded-2xl border border-slate-200 shadow-xs">
            {/* City / Location Selector */}
            <div className="flex items-center justify-between gap-2 mb-3 pb-3 border-b border-slate-100 flex-wrap">
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700">
                <MapPin className="w-4 h-4 text-emerald-600" />
                <span>City:</span>
              </div>
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
                {cities.map((c) => (
                  <button
                    key={c}
                    onClick={() => setSelectedCity(c)}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition ${
                      selectedCity === c
                        ? 'bg-emerald-600 text-white shadow-xs'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>

            <div className="relative mb-4">
              <Search className="w-5 h-5 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search doctors, clinic names, specialty, or localities..."
                className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-hidden"
              />
            </div>

            {/* Specialty Quick Chips */}
            <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
              {specialties.map((s) => (
                <button
                  key={s}
                  onClick={() => setSelectedSpecialty(s)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition ${
                    selectedSpecialty === s
                      ? 'bg-emerald-600 text-white shadow-xs'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Doctor Cards Grid */}
          {loadingDoctors ? (
            <div className="text-center py-12 text-slate-500 text-sm">
              Finding verified clinics and doctors...
            </div>
          ) : filteredDoctors.length === 0 ? (
            <div className="text-center py-12 bg-white rounded-2xl border border-slate-200 p-8">
              <Compass className="w-10 h-10 text-slate-400 mx-auto mb-2" />
              <p className="text-sm font-bold text-slate-700">No doctors found matching filters</p>
              <p className="text-xs text-slate-400 mt-1">
                Try selecting "All" or searching a different locality
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {filteredDoctors.map((doc) => (
                <div
                  key={doc.doctor_id}
                  className="bg-white rounded-2xl p-5 border border-slate-200 shadow-xs hover:shadow-md transition flex flex-col justify-between"
                >
                  <div>
                    {/* Top Row */}
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div>
                        <h3 className="text-base font-bold text-slate-900 flex items-center gap-1.5">
                          {doc.full_name}
                          <Sparkles className="w-4 h-4 text-emerald-500 fill-emerald-500" />
                        </h3>
                        <p className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md inline-block mt-1">
                          {doc.specialty} • {doc.years_experience} yrs exp
                        </p>
                      </div>
                      <div className="text-right">
                        <span className="text-sm font-bold text-slate-900">
                          ₹{doc.in_person_fee}
                        </span>
                        <div className="text-[10px] text-slate-400">Consultation Fee</div>
                      </div>
                    </div>

                    {/* Bio */}
                    {doc.bio && (
                      <p className="text-xs text-slate-600 line-clamp-2 mb-3">{doc.bio}</p>
                    )}

                    {/* Clinic Information */}
                    {doc.clinic && (
                      <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 mb-4 space-y-1">
                        <div className="text-xs font-bold text-slate-800 flex items-center gap-1">
                          <MapPin className="w-3.5 h-3.5 text-red-500 shrink-0" />
                          {doc.clinic.name}
                        </div>
                        <p className="text-[11px] text-slate-500 pl-4.5 line-clamp-1">
                          {doc.clinic.address}, {doc.clinic.locality}, {doc.clinic.city}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 pt-2 border-t border-slate-100">
                    {/* 1-Click Google Maps Link */}
                    {doc.google_maps_url && (
                      <a
                        href={doc.google_maps_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-1 py-2 px-3 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl flex items-center justify-center gap-1.5 transition text-center"
                      >
                        <MapPin className="w-3.5 h-3.5 text-emerald-600" />
                        Directions
                      </a>
                    )}

                    {/* Book Slot */}
                    <button
                      onClick={() => handleOpenBooking(doc)}
                      className="flex-1 py-2 px-3 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow-xs transition flex items-center justify-center gap-1"
                    >
                      <Calendar className="w-3.5 h-3.5" />
                      Book Visit
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Booking Modal */}
          {selectedDoctor && (
            <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
              <div className="bg-white rounded-3xl shadow-xl max-w-lg w-full p-6 border border-slate-200">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
                  <div>
                    <h3 className="text-base font-bold text-slate-900">
                      Book with {selectedDoctor.full_name}
                    </h3>
                    <p className="text-xs text-slate-500">
                      {selectedDoctor.clinic?.name || 'In-Person Consultation'}
                    </p>
                  </div>
                  <button
                    onClick={() => setSelectedDoctor(null)}
                    className="p-1 text-slate-400 hover:text-slate-700 rounded-full"
                  >
                    <XCircle className="w-5 h-5" />
                  </button>
                </div>

                {bookingSuccess ? (
                  <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl text-center space-y-2">
                    <CheckCircle2 className="w-10 h-10 text-emerald-600 mx-auto" />
                    <p className="text-xs font-bold text-emerald-900">{bookingSuccess}</p>
                    <p className="text-[11px] text-emerald-700">Redirecting to appointments...</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* Pay at clinic badge */}
                    <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between">
                      <div>
                        <div className="text-xs font-bold text-emerald-900">
                          Pay-at-Clinic Guaranteed
                        </div>
                        <div className="text-[11px] text-emerald-700">
                          Pay ₹{selectedDoctor.in_person_fee} upon arrival. No advance online payment
                          needed.
                        </div>
                      </div>
                      <span className="text-xs font-extrabold text-emerald-800 bg-white px-2.5 py-1 rounded-lg border border-emerald-300">
                        ₹{selectedDoctor.in_person_fee}
                      </span>
                    </div>

                    {/* Date Selector */}
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">
                        Select Visit Date
                      </label>
                      <input
                        type="date"
                        value={bookingDate}
                        min={new Date().toISOString().split('T')[0]}
                        onChange={(e) => {
                          setBookingDate(e.target.value)
                          loadSlots(selectedDoctor.doctor_id, e.target.value)
                        }}
                        className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs focus:ring-2 focus:ring-emerald-500 focus:outline-hidden"
                      />
                    </div>

                    {/* Available Time Slots */}
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1.5">
                        Available 15-Min Slots
                      </label>
                      {slots.length === 0 ? (
                        <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-center text-xs text-slate-500">
                          No open slots on this date. Doctor may be unavailable.
                        </div>
                      ) : (
                        <div className="grid grid-cols-4 gap-2 max-h-40 overflow-y-auto p-1">
                          {slots.map((slot) => {
                            const timeLabel = slot.start_time.slice(11, 16) || slot.start_time
                            const isSelected = selectedSlot === timeLabel
                            return (
                              <button
                                key={slot.start_time}
                                type="button"
                                disabled={!slot.is_available}
                                onClick={() => setSelectedSlot(timeLabel)}
                                className={`py-2 text-xs font-semibold rounded-xl border transition ${
                                  isSelected
                                    ? 'bg-emerald-600 text-white border-emerald-600 shadow-xs'
                                    : slot.is_available
                                      ? 'bg-white text-slate-700 border-slate-200 hover:border-emerald-500'
                                      : 'bg-slate-100 text-slate-300 border-slate-200 cursor-not-allowed'
                                }`}
                              >
                                {timeLabel}
                              </button>
                            )
                          })}
                        </div>
                      )}
                    </div>

                    {/* Reason / Symptoms notes */}
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">
                        Reason for Visit / Symptoms (Optional)
                      </label>
                      <input
                        type="text"
                        value={bookingNotes}
                        onChange={(e) => setBookingNotes(e.target.value)}
                        placeholder="e.g. Mild fever, skin irritation..."
                        className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs focus:ring-2 focus:ring-emerald-500 focus:outline-hidden"
                      />
                    </div>

                    {/* Confirm Button */}
                    <button
                      type="button"
                      disabled={!selectedSlot || bookingSubmitting}
                      onClick={handleConfirmBooking}
                      className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow-md transition disabled:opacity-50"
                    >
                      {bookingSubmitting ? 'Confirming...' : 'Confirm Appointment (Pay at Clinic)'}
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: MY APPOINTMENTS */}
      {activeTab === 'appointments' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-base font-bold text-slate-900">Your Clinic Appointments</h2>
            <button
              onClick={loadAppointments}
              className="text-xs text-emerald-600 hover:underline font-semibold"
            >
              Refresh
            </button>
          </div>

          {loadingAppointments ? (
            <div className="text-center py-12 text-slate-400 text-sm">Loading appointments...</div>
          ) : appointments.length === 0 ? (
            <div className="p-8 bg-white border border-slate-200 rounded-2xl text-center">
              <Calendar className="w-10 h-10 text-slate-400 mx-auto mb-2" />
              <p className="text-sm font-bold text-slate-700">No appointments scheduled</p>
              <button
                onClick={() => setActiveTab('find')}
                className="mt-3 px-4 py-1.5 bg-emerald-600 text-white text-xs font-bold rounded-xl shadow-xs"
              >
                Find a Doctor
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {appointments.map((apt) => {
                const isCompleted = apt.status === 'completed'
                const isCancelled = apt.status === 'cancelled'
                return (
                  <div
                    key={apt.id}
                    className="p-4 bg-white rounded-2xl border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-slate-900">
                          {apt.doctor_name || 'Doctor Appointment'}
                        </span>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full capitalize ${
                            apt.status === 'confirmed'
                              ? 'bg-emerald-100 text-emerald-800'
                              : apt.status === 'completed'
                                ? 'bg-blue-100 text-blue-800'
                                : apt.status === 'cancelled'
                                  ? 'bg-red-100 text-red-800'
                                  : 'bg-amber-100 text-amber-800'
                          }`}
                        >
                          {apt.status.replace('_', ' ')}
                        </span>
                      </div>

                      <div className="text-xs text-slate-500 flex items-center gap-3">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5 text-slate-400" />
                          {new Date(apt.slot_start).toLocaleDateString()} at{' '}
                          {new Date(apt.slot_start).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                        <span className="font-semibold text-slate-700">
                          Fee: ₹{apt.fee_amount} (Pay at Clinic)
                        </span>
                      </div>

                      {apt.clinic_name && (
                        <div className="text-xs text-slate-600 flex items-center gap-1">
                          <MapPin className="w-3.5 h-3.5 text-red-500" />
                          {apt.clinic_name} {apt.clinic_address && `— ${apt.clinic_address}`}
                        </div>
                      )}
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-2">
                      {apt.google_maps_url && (
                        <a
                          href={apt.google_maps_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-xl flex items-center gap-1 transition"
                        >
                          <MapPin className="w-3.5 h-3.5 text-emerald-600" />
                          Directions
                        </a>
                      )}

                      {isCompleted && (
                        <button
                          onClick={() =>
                            alert(
                              `Downloading official signed vector prescription PDF for appointment ${apt.id}...`
                            )
                          }
                          className="px-3 py-1.5 bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 text-xs font-bold rounded-xl flex items-center gap-1 transition"
                        >
                          <Download className="w-3.5 h-3.5" />
                          Signed Rx PDF
                        </button>
                      )}

                      {!isCompleted && !isCancelled && (
                        <button
                          onClick={() => handleCancelBooking(apt.id)}
                          className="px-3 py-1.5 text-red-600 hover:bg-red-50 text-xs font-semibold rounded-xl border border-red-200 transition"
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: HEALTH DOCUMENT VAULT */}
      {activeTab === 'vault' && (
        <div className="space-y-6">
          {/* Upload Form */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs">
            <h3 className="text-sm font-bold text-slate-900 mb-2 flex items-center gap-2">
              <Upload className="w-4 h-4 text-emerald-600" />
              Upload Medical Report or Prescription
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Stored securely with Indian data sovereignty in AWS <code>ap-south-1</code> (MinIO/S3
              encrypted).
            </p>

            <form onSubmit={handleUploadDocument} className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Document Type
                </label>
                <select
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs bg-white focus:outline-hidden"
                >
                  <option value="lab_report">Lab Test Report</option>
                  <option value="past_prescription">Past Prescription</option>
                  <option value="scan">X-Ray / MRI Scan</option>
                  <option value="medical_history">Medical History Summary</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Select File (PDF/Image)
                </label>
                <input
                  type="file"
                  required
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-slate-500 file:mr-2 file:py-1.5 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Notes</label>
                <input
                  type="text"
                  value={docNotes}
                  onChange={(e) => setDocNotes(e.target.value)}
                  placeholder="e.g. Fasting blood sugar report"
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs focus:outline-hidden"
                />
              </div>

              <div className="sm:col-span-3 flex justify-end">
                <button
                  type="submit"
                  disabled={!uploadFile || uploading}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow-xs transition disabled:opacity-50 flex items-center gap-1.5"
                >
                  {uploading ? 'Uploading to S3...' : 'Upload to Vault'}
                  <FolderLock className="w-3.5 h-3.5" />
                </button>
              </div>
            </form>
          </div>

          {/* Stored Documents Feed */}
          <div className="space-y-3">
            <h3 className="text-sm font-bold text-slate-900">Your Secure Medical Files</h3>
            {vaultDocs.length === 0 ? (
              <div className="p-8 bg-white border border-slate-200 rounded-2xl text-center text-xs text-slate-400">
                No documents uploaded yet. Upload your past prescriptions or lab results above.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {vaultDocs.map((doc) => (
                  <div
                    key={doc.id}
                    className="p-4 bg-white rounded-2xl border border-slate-200 shadow-xs flex items-start justify-between"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-1.5">
                        <FileText className="w-4 h-4 text-emerald-600" />
                        <span className="text-xs font-bold text-slate-900 truncate max-w-40">
                          {doc.file_name}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 capitalize">
                        {doc.doc_type.replace('_', ' ')} • {(doc.file_size_bytes / 1024).toFixed(1)}{' '}
                        KB
                      </p>
                      {doc.notes && <p className="text-[11px] text-slate-600">{doc.notes}</p>}
                    </div>

                    <a
                      href={doc.download_url || `http://192.168.10.39:9000/patient-documents/${doc.s3_key}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100"
                    >
                      <Download className="w-4 h-4" />
                    </a>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Doctor Prescriptions */}
          <div className="space-y-3">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-emerald-600" />
              Doctor Prescriptions (Digitally Signed)
            </h3>
            {prescriptions.length === 0 ? (
              <div className="p-6 bg-white border border-slate-200 rounded-2xl text-center text-xs text-slate-400">
                No official prescriptions issued yet. Once your doctor completes a consultation, digitally signed prescriptions will appear here.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {prescriptions.map((rx) => (
                  <div
                    key={rx.id}
                    className="p-4 bg-white rounded-2xl border border-slate-200 shadow-xs space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-bold text-slate-900">Diagnosis: {rx.diagnosis}</div>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 capitalize">
                        {rx.dispense_status}
                      </span>
                    </div>
                    {rx.clinical_notes && (
                      <p className="text-[11px] text-slate-500 italic">{rx.clinical_notes}</p>
                    )}
                    <div className="text-[11px] text-slate-600">
                      <strong>Medicines:</strong> {rx.items?.map((i: PrescriptionItem) => `${i.medicine_name} (${i.dosage})`).join(', ')}
                    </div>
                    <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-400">
                      <span>Hash: {rx.digital_signature?.slice(0, 10)}...</span>
                      {rx.pdf_s3_key && (
                        <a
                          href={`http://192.168.10.39:9000/prescriptions/${rx.pdf_s3_key}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="px-2.5 py-1 bg-emerald-50 text-emerald-700 font-bold rounded-lg hover:bg-emerald-100 flex items-center gap-1 text-[11px]"
                        >
                          <Download className="w-3 h-3" />
                          Download Rx PDF
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
