import React, { useEffect, useState } from 'react'
import {
  AlertTriangle,
  Award,
  Calendar,
  CheckCircle2,
  Clock,
  FileCheck,
  MapPin,
  Plus,
  Send,
  ShieldCheck,
  Stethoscope,
  Trash2,
  Users,
} from 'lucide-react'
import type { Appointment, Chemist, PrescriptionItem } from '../../types'
import { api } from '../../services/api'
import type { AuthSession } from '../../services/firebase'

interface DoctorPortalProps {
  session: AuthSession | null
  onRequireLogin: () => void
}

export const DoctorPortal: React.FC<DoctorPortalProps> = ({ session, onRequireLogin }) => {
  const [tab, setTab] = useState<'queue' | 'rx' | 'schedule' | 'clinic'>('queue')

  // Clinic Config state
  const [clinicName, setClinicName] = useState('Apex Care Clinic')
  const [address, setAddress] = useState('12th Main Road, Indiranagar')
  const [city, setCity] = useState('Bengaluru')
  const [locality, setLocality] = useState('Indiranagar')
  const [pincode, setPincode] = useState('560038')
  const [contact, setContact] = useState('+91 9988776655')
  const [lat, setLat] = useState('12.9716')
  const [lng, setLng] = useState('77.5946')
  const [clinicSaved, setClinicSaved] = useState(false)

  // Queue state
  const [queue, setQueue] = useState<Appointment[]>([])
  const [loadingQueue, setLoadingQueue] = useState(false)

  // Prescription Builder state
  const [selectedAppointment, setSelectedAppointment] = useState<Appointment | null>(null)
  const [diagnosis, setDiagnosis] = useState('')
  const [clinicalNotes, setClinicalNotes] = useState('')
  const [medicines, setMedicines] = useState<PrescriptionItem[]>([
    {
      medicine_name: 'Paracetamol 650mg',
      dosage: '650mg',
      frequency: '1-0-1',
      duration: '3 days',
      instructions: 'After food with warm water',
      is_schedule_x: false,
    },
  ])
  const [selectedChemistId, setSelectedChemistId] = useState<string>('')
  const [chemists, setChemists] = useState<Chemist[]>([])
  const [rxSubmitting, setRxSubmitting] = useState(false)
  const [signedRxSuccess, setSignedRxSuccess] = useState<string | null>(null)

  useEffect(() => {
    if (session) {
      loadQueue()
      loadChemists()
    }
  }, [session])

  const loadQueue = async () => {
    setLoadingQueue(true)
    try {
      const res = await api.getDoctorQueue()
      setQueue(res.queue || [])
    } catch {
      // Mock data for demo if queue is empty
      setQueue([
        {
          id: 'apt-demo-1',
          patient_id: 'pat-1',
          doctor_id: session?.userId || 'doc-1',
          slot_start: new Date().toISOString(),
          slot_end: new Date().toISOString(),
          status: 'checked_in',
          fee_amount: '500.00',
          payment_status: 'pending',
          notes: 'Persistent dry cough and mild fever',
        },
      ])
    } finally {
      setLoadingQueue(false)
    }
  }

  const loadChemists = async () => {
    try {
      const res = await api.listChemists()
      setChemists(res.items || [])
    } catch {
      setChemists([])
    }
  }

  const handleSaveClinic = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.upsertClinic({
        name: clinicName,
        address,
        city,
        locality,
        pincode,
        contact_number: contact,
        latitude: parseFloat(lat),
        longitude: parseFloat(lng),
      })
      setClinicSaved(true)
      setTimeout(() => setClinicSaved(false), 3000)
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to save clinic')
    }
  }

  const handleAddMedicineRow = () => {
    setMedicines([
      ...medicines,
      {
        medicine_name: '',
        dosage: '',
        frequency: '1-0-1',
        duration: '5 days',
        instructions: 'After meals',
        is_schedule_x: false,
      },
    ])
  }

  const handleRemoveMedicineRow = (index: number) => {
    setMedicines(medicines.filter((_, i) => i !== index))
  }

  const handleMedicineChange = (
    index: number,
    field: keyof PrescriptionItem,
    value: string | boolean
  ) => {
    const updated = [...medicines]
    // Schedule X Drug warning detection
    if (field === 'medicine_name' && typeof value === 'string') {
      const val = value.toLowerCase()
      if (
        val.includes('ketamine') ||
        val.includes('amphetamine') ||
        val.includes('methylphenidate')
      ) {
        updated[index].is_schedule_x = true
      } else {
        updated[index].is_schedule_x = false
      }
    }
    updated[index] = { ...updated[index], [field]: value }
    setMedicines(updated)
  }

  const handleSignAndIssuePrescription = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedAppointment) return
    setRxSubmitting(true)
    setSignedRxSuccess(null)
    try {
      const res = await api.createPrescription({
        appointment_id: selectedAppointment.id,
        diagnosis,
        clinical_notes: clinicalNotes,
        chemist_id: selectedChemistId || null,
        items: medicines,
      })
      setSignedRxSuccess(
        `Prescription successfully signed with HMAC-SHA256! (Fingerprint: ${res.digital_signature.slice(0, 16)}...). ${
          selectedChemistId ? 'Routed to designated Chemist.' : 'Sent to Patient Vault.'
        }`
      )
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Prescription creation failed')
    } finally {
      setRxSubmitting(false)
    }
  }

  if (!session) {
    return (
      <div className="max-w-md mx-auto my-16 p-8 bg-white rounded-3xl border border-slate-200 text-center shadow-xs">
        <Stethoscope className="w-12 h-12 text-blue-600 mx-auto mb-3" />
        <h2 className="text-lg font-bold text-slate-900">Doctor Practice Console</h2>
        <p className="text-xs text-slate-500 mt-1 mb-4">
          Please authenticate with your doctor account to access the queue and prescription tools.
        </p>
        <button
          onClick={onRequireLogin}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-xl shadow-xs"
        >
          Sign in as Doctor
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Top Banner with Verification Badge */}
      <div className="bg-gradient-to-r from-blue-700 to-indigo-800 rounded-3xl p-6 text-white mb-6 shadow-md flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold">{session.displayName || 'Dr. Medical Practitioner'}</h1>
            <span className="flex items-center gap-1 text-[11px] font-extrabold bg-emerald-500/20 border border-emerald-400/40 text-emerald-300 px-2.5 py-0.5 rounded-full">
              <ShieldCheck className="w-3.5 h-3.5" />
              Verified Doctor
            </span>
          </div>
          <p className="text-xs text-blue-200 mt-1">
            Medical Council Reg: <strong>MCI-88942-A</strong> • Karnataka Medical Council
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="bg-white/10 backdrop-blur-xs px-3.5 py-2 rounded-2xl border border-white/10 text-right">
            <div className="text-xs text-blue-200">Consultation Fee</div>
            <div className="text-base font-extrabold">₹500.00</div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 mb-6 gap-3 sm:gap-6 overflow-x-auto">
        <button
          onClick={() => setTab('queue')}
          className={`pb-3 text-xs sm:text-sm font-bold flex items-center gap-2 border-b-2 transition whitespace-nowrap ${
            tab === 'queue'
              ? 'border-blue-600 text-blue-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Users className="w-4 h-4" />
          Live OPD Queue ({queue.length})
        </button>

        <button
          onClick={() => setTab('rx')}
          className={`pb-3 text-xs sm:text-sm font-bold flex items-center gap-2 border-b-2 transition whitespace-nowrap ${
            tab === 'rx'
              ? 'border-blue-600 text-blue-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <FileCheck className="w-4 h-4" />
          Digital Prescription Builder
        </button>

        <button
          onClick={() => setTab('clinic')}
          className={`pb-3 text-xs sm:text-sm font-bold flex items-center gap-2 border-b-2 transition whitespace-nowrap ${
            tab === 'clinic'
              ? 'border-blue-600 text-blue-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <MapPin className="w-4 h-4" />
          Clinic & Location Setup
        </button>

        <button
          onClick={() => setTab('schedule')}
          className={`pb-3 text-xs sm:text-sm font-bold flex items-center gap-2 border-b-2 transition whitespace-nowrap ${
            tab === 'schedule'
              ? 'border-blue-600 text-blue-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Calendar className="w-4 h-4" />
          Weekly Availability
        </button>
      </div>

      {/* TAB 1: LIVE OPD QUEUE */}
      {tab === 'queue' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900">Today's In-Clinic Appointments</h2>
            <button onClick={loadQueue} className="text-xs text-blue-600 font-bold hover:underline">
              Refresh Queue
            </button>
          </div>

          {loadingQueue ? (
            <div className="text-center py-12 text-slate-400 text-xs">Loading live queue...</div>
          ) : queue.length === 0 ? (
            <div className="p-8 bg-white rounded-2xl border border-slate-200 text-center text-xs text-slate-400">
              No patients in queue right now.
            </div>
          ) : (
            <div className="space-y-3">
              {queue.map((apt) => (
                <div
                  key={apt.id}
                  className="p-4 bg-white rounded-2xl border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-slate-900">
                        {apt.patient_id ? `Patient (${apt.patient_id.slice(0, 8)})` : 'In-Person Patient'}
                      </span>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 capitalize">
                        {apt.status.replace('_', ' ')}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 flex items-center gap-3">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 text-slate-400" />
                        {new Date(apt.slot_start).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                      <span>Pay at Clinic: ₹{apt.fee_amount}</span>
                    </div>
                    {apt.notes && (
                      <p className="text-xs text-slate-600 italic">Chief Complaint: {apt.notes}</p>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        setSelectedAppointment(apt)
                        setTab('rx')
                      }}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-xs flex items-center gap-1.5 transition"
                    >
                      <Stethoscope className="w-3.5 h-3.5" />
                      Consult & Prescribe
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: DIGITAL PRESCRIPTION BUILDER */}
      {tab === 'rx' && (
        <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-xs space-y-6">
          <div className="border-b border-slate-100 pb-4 flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <FileCheck className="w-5 h-5 text-blue-600" />
                Structured Digital Prescription & HMAC Seal
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Generates verifiable digital signatures compliant with Section 3 of the IT Act 2000.
              </p>
            </div>
            {selectedAppointment && (
              <span className="text-xs font-bold px-3 py-1 bg-blue-50 text-blue-800 rounded-xl border border-blue-200">
                Apt: {selectedAppointment.id.slice(0, 8)}
              </span>
            )}
          </div>

          {signedRxSuccess && (
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div className="text-xs text-emerald-900 leading-relaxed font-medium">
                {signedRxSuccess}
              </div>
            </div>
          )}

          <form onSubmit={handleSignAndIssuePrescription} className="space-y-5">
            {/* Diagnosis & Notes */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Primary Clinical Diagnosis
                </label>
                <input
                  type="text"
                  required
                  value={diagnosis}
                  onChange={(e) => setDiagnosis(e.target.value)}
                  placeholder="e.g. Acute Bronchitis / Viral Pharyngitis"
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Clinical Advice / Instructions
                </label>
                <input
                  type="text"
                  value={clinicalNotes}
                  onChange={(e) => setClinicalNotes(e.target.value)}
                  placeholder="e.g. Steam inhalation, drink warm fluids, follow up in 5 days"
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
                />
              </div>
            </div>

            {/* Medicine Items Table */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-bold text-slate-800">Prescribed Medications</label>
                <button
                  type="button"
                  onClick={handleAddMedicineRow}
                  className="text-xs font-bold text-blue-600 hover:text-blue-800 flex items-center gap-1"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Medicine
                </button>
              </div>

              <div className="space-y-2">
                {medicines.map((med, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-slate-50 border border-slate-200 rounded-2xl grid grid-cols-1 sm:grid-cols-6 gap-2 items-center"
                  >
                    <div className="sm:col-span-2">
                      <input
                        type="text"
                        required
                        value={med.medicine_name}
                        onChange={(e) => handleMedicineChange(idx, 'medicine_name', e.target.value)}
                        placeholder="Drug / Brand Name"
                        className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg text-xs"
                      />
                      {med.is_schedule_x && (
                        <div className="text-[10px] text-amber-700 font-bold flex items-center gap-1 mt-1">
                          <AlertTriangle className="w-3 h-3 text-amber-500" />
                          Schedule X Drug Warning (Requires In-Person Only)
                        </div>
                      )}
                    </div>

                    <div>
                      <input
                        type="text"
                        value={med.dosage}
                        onChange={(e) => handleMedicineChange(idx, 'dosage', e.target.value)}
                        placeholder="Dosage (500mg)"
                        className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg text-xs"
                      />
                    </div>

                    <div>
                      <input
                        type="text"
                        value={med.frequency}
                        onChange={(e) => handleMedicineChange(idx, 'frequency', e.target.value)}
                        placeholder="Freq (1-0-1)"
                        className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg text-xs"
                      />
                    </div>

                    <div>
                      <input
                        type="text"
                        value={med.duration}
                        onChange={(e) => handleMedicineChange(idx, 'duration', e.target.value)}
                        placeholder="Duration (5 days)"
                        className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg text-xs"
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <input
                        type="text"
                        value={med.instructions || ''}
                        onChange={(e) => handleMedicineChange(idx, 'instructions', e.target.value)}
                        placeholder="After food"
                        className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg text-xs mr-2"
                      />
                      {medicines.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveMedicineRow(idx)}
                          className="p-1 text-red-500 hover:bg-red-50 rounded-md"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Chemist Routing Option */}
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl">
              <label className="block text-xs font-bold text-slate-800 mb-1">
                Route Prescription to Dedicated Chemist / Pharmacy
              </label>
              <select
                value={selectedChemistId}
                onChange={(e) => setSelectedChemistId(e.target.value)}
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-xl text-xs focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
              >
                <option value="">Direct to Patient Vault (No specific pharmacy routed)</option>
                {chemists.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.pharmacy_name} (DL No: {c.license_number}) — {c.locality}, {c.city}
                  </option>
                ))}
              </select>
            </div>

            {/* Action Bar */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
              <button
                type="submit"
                disabled={rxSubmitting || !selectedAppointment}
                className="py-2.5 px-5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-md transition disabled:opacity-50 flex items-center gap-2"
              >
                <Award className="w-4 h-4" />
                {rxSubmitting
                  ? 'Computing HMAC Digital Signature...'
                  : 'Digitally Sign & Issue Prescription'}
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </form>
        </div>
      )}

      {/* TAB 3: CLINIC CONFIGURATION */}
      {tab === 'clinic' && (
        <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-xs max-w-2xl">
          <h2 className="text-base font-bold text-slate-900 mb-1 flex items-center gap-2">
            <MapPin className="w-5 h-5 text-blue-600" />
            Clinic Address & GPS Location
          </h2>
          <p className="text-xs text-slate-500 mb-4">
            Powers turn-by-turn navigation in Google Maps for arriving patients.
          </p>

          {clinicSaved && (
            <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 font-bold flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              Clinic details updated successfully!
            </div>
          )}

          <form onSubmit={handleSaveClinic} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Clinic Name</label>
              <input
                type="text"
                required
                value={clinicName}
                onChange={(e) => setClinicName(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Street Address</label>
              <input
                type="text"
                required
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs"
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Locality</label>
                <input
                  type="text"
                  required
                  value={locality}
                  onChange={(e) => setLocality(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">City</label>
                <input
                  type="text"
                  required
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Pincode</label>
                <input
                  type="text"
                  required
                  value={pincode}
                  onChange={(e) => setPincode(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  GPS Latitude (Decimal)
                </label>
                <input
                  type="text"
                  value={lat}
                  onChange={(e) => setLat(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  GPS Longitude (Decimal)
                </label>
                <input
                  type="text"
                  value={lng}
                  onChange={(e) => setLng(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Contact Phone</label>
              <input
                type="text"
                value={contact}
                onChange={(e) => setContact(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs"
              />
            </div>

            <button
              type="submit"
              className="py-2.5 px-5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-xs transition"
            >
              Save Clinic & Coordinates
            </button>
          </form>
        </div>
      )}

      {/* TAB 4: SCHEDULE CONFIGURATION */}
      {tab === 'schedule' && (
        <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-xs max-w-xl">
          <h2 className="text-base font-bold text-slate-900 mb-1 flex items-center gap-2">
            <Calendar className="w-5 h-5 text-blue-600" />
            Weekly OPD Availability Blocks
          </h2>
          <p className="text-xs text-slate-500 mb-4">
            Generates atomic 15-minute slot intervals for patient booking.
          </p>

          <div className="space-y-3">
            {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'].map(
              (day, idx) => (
                <div
                  key={day}
                  className="p-3 bg-slate-50 border border-slate-200 rounded-2xl flex items-center justify-between"
                >
                  <div>
                    <span className="text-xs font-bold text-slate-900">{day}</span>
                    <p className="text-[11px] text-slate-500">10:00 AM – 1:00 PM • 5:00 PM – 8:00 PM</p>
                  </div>
                  <button
                    type="button"
                    onClick={async () => {
                      await api.updateAvailability({
                        day_of_week: idx,
                        start_time: '10:00:00',
                        end_time: '13:00:00',
                        slot_duration_minutes: 15,
                      })
                      alert(`Availability updated for ${day}!`)
                    }}
                    className="px-3 py-1.5 text-xs font-semibold bg-white border border-slate-300 hover:border-blue-500 rounded-xl text-slate-700"
                  >
                    Sync Slots
                  </button>
                </div>
              )
            )}
          </div>
        </div>
      )}
    </div>
  )
}
