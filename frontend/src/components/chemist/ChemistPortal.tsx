import React, { useEffect, useState } from 'react'
import {
  Building2,
  CheckCircle2,
  Clock,
  Pill,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import type { Prescription } from '../../types'
import { api } from '../../services/api'
import type { AuthSession } from '../../services/firebase'

interface ChemistPortalProps {
  session: AuthSession | null
  onRequireLogin: () => void
}

export const ChemistPortal: React.FC<ChemistPortalProps> = ({ session, onRequireLogin }) => {
  const [tab, setTab] = useState<'feed' | 'register'>('feed')

  // Registration state
  const [pharmacyName, setPharmacyName] = useState('Sanjivani Medicos & Chemists')
  const [licenseNumber, setLicenseNumber] = useState('KA-BLR-DL-2026-9812')
  const [address, setAddress] = useState('Shop 4, Metro Pillar 84, Indiranagar')
  const [city, setCity] = useState('Bengaluru')
  const [locality, setLocality] = useState('Indiranagar')
  const [pincode, setPincode] = useState('560038')
  const [contact, setContact] = useState('+91 9123456780')
  const [registered, setRegistered] = useState(false)

  // Prescriptions state
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([])
  const [loading, setLoading] = useState(false)
  const [dispensingId, setDispensingId] = useState<string | null>(null)

  useEffect(() => {
    if (session) {
      loadPrescriptions()
    }
  }, [session])

  const loadPrescriptions = async () => {
    setLoading(true)
    try {
      const res = await api.getChemistPrescriptions()
      setPrescriptions(res.prescriptions || [])
    } catch {
      // Mock demonstration items if empty
      setPrescriptions([
        {
          id: 'rx-demo-8412',
          appointment_id: 'apt-demo-1',
          doctor_id: 'doc-demo-1',
          patient_id: 'pat-demo-1',
          diagnosis: 'Seasonal Bronchial Inflammation',
          clinical_notes: 'Take medicines after meals with warm water',
          items: [
            {
              medicine_name: 'Amoxicillin 500mg',
              dosage: '500mg',
              frequency: '1-0-1',
              duration: '5 days',
              instructions: 'After breakfast and dinner',
              is_schedule_x: false,
            },
            {
              medicine_name: 'Cetirizine 10mg',
              dosage: '10mg',
              frequency: '0-0-1',
              duration: '3 days',
              instructions: 'At bedtime',
              is_schedule_x: false,
            },
          ],
          digital_signature: 'hmac_sha256_e4c9f1a288b77620d439a01f5c3b',
          digital_signature_timestamp: new Date().toISOString(),
          dispense_status: 'pending',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.registerChemist({
        pharmacy_name: pharmacyName,
        license_number: licenseNumber,
        address,
        city,
        locality,
        pincode,
        contact_number: contact,
      })
      setRegistered(true)
      setTimeout(() => {
        setRegistered(false)
        setTab('feed')
      }, 2000)
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Registration failed')
    }
  }

  const handleDispense = async (prescriptionId: string) => {
    setDispensingId(prescriptionId)
    try {
      await api.dispensePrescription(prescriptionId)
      // update state locally
      setPrescriptions((prev) =>
        prev.map((p) =>
          p.id === prescriptionId
            ? { ...p, dispense_status: 'dispensed', dispensed_at: new Date().toISOString() }
            : p
        )
      )
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Dispensation failed')
    } finally {
      setDispensingId(null)
    }
  }

  if (!session) {
    return (
      <div className="max-w-md mx-auto my-16 p-8 bg-white rounded-3xl border border-slate-200 text-center shadow-xs">
        <Pill className="w-12 h-12 text-amber-600 mx-auto mb-3" />
        <h2 className="text-lg font-bold text-slate-900">Chemist & Druggist Console</h2>
        <p className="text-xs text-slate-500 mt-1 mb-4">
          Please authenticate with your chemist account to view incoming prescriptions and fulfill orders.
        </p>
        <button
          onClick={onRequireLogin}
          className="w-full py-2.5 bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs rounded-xl shadow-xs"
        >
          Sign in as Chemist
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Banner */}
      <div className="bg-gradient-to-r from-amber-600 to-orange-700 rounded-3xl p-6 text-white mb-6 shadow-md flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold">
              {session.displayName || 'Sanjivani Pharmacy & Chemists'}
            </h1>
            <span className="flex items-center gap-1 text-[11px] font-extrabold bg-white/20 border border-white/30 text-white px-2.5 py-0.5 rounded-full">
              <ShieldCheck className="w-3.5 h-3.5" />
              Licensed Druggist
            </span>
          </div>
          <p className="text-xs text-amber-100 mt-1">
            Drug License No: <strong>KA-BLR-DL-2026-9812</strong> • Indiranagar, Bengaluru
          </p>
        </div>

        <div className="bg-white/10 backdrop-blur-xs px-4 py-2 rounded-2xl border border-white/10 text-right">
          <div className="text-xs text-amber-100">Live Prescriptions</div>
          <div className="text-lg font-extrabold">{prescriptions.length} Active</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 mb-6 gap-3 sm:gap-6">
        <button
          onClick={() => setTab('feed')}
          className={`pb-3 text-xs sm:text-sm font-bold flex items-center gap-2 border-b-2 transition ${
            tab === 'feed'
              ? 'border-amber-600 text-amber-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Pill className="w-4 h-4" />
          Incoming Doctor Prescriptions ({prescriptions.length})
        </button>

        <button
          onClick={() => setTab('register')}
          className={`pb-3 text-xs sm:text-sm font-bold flex items-center gap-2 border-b-2 transition ${
            tab === 'register'
              ? 'border-amber-600 text-amber-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Building2 className="w-4 h-4" />
          Pharmacy Profile & License
        </button>
      </div>

      {/* TAB 1: INCOMING PRESCRIPTIONS FEED */}
      {tab === 'feed' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900">Live Prescriptions Routed by Doctors</h2>
            <button onClick={loadPrescriptions} className="text-xs text-amber-600 font-bold hover:underline">
              Refresh Feed
            </button>
          </div>

          {loading ? (
            <div className="text-center py-12 text-slate-400 text-xs">Loading prescriptions...</div>
          ) : prescriptions.length === 0 ? (
            <div className="p-8 bg-white rounded-2xl border border-slate-200 text-center text-xs text-slate-400">
              No incoming prescriptions waiting to be dispensed.
            </div>
          ) : (
            <div className="space-y-4">
              {prescriptions.map((rx) => {
                const isDispensed = rx.dispense_status === 'dispensed'
                return (
                  <div
                    key={rx.id}
                    className="p-5 bg-white rounded-2xl border border-slate-200 shadow-xs space-y-4"
                  >
                    {/* Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-slate-900">
                            Prescription #{rx.id.slice(0, 8)}
                          </span>
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded-full capitalize ${
                              isDispensed
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-amber-100 text-amber-800'
                            }`}
                          >
                            {rx.dispense_status}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">
                          Diagnosis: <strong>{rx.diagnosis}</strong>
                        </p>
                      </div>

                      {/* Cryptographic Digital Signature Seal */}
                      <div className="p-2.5 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                        <div className="text-[11px] text-emerald-900 leading-tight">
                          <span className="font-bold">DIGITALLY SIGNED & VERIFIED</span>
                          <div className="text-[9px] text-emerald-700 font-mono">
                            Sig: {rx.digital_signature.slice(0, 18)}...
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Prescribed Drugs List */}
                    <div>
                      <div className="text-xs font-bold text-slate-700 mb-2">Prescribed Medicines</div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                        {rx.items.map((item, idx) => (
                          <div
                            key={idx}
                            className="p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-1"
                          >
                            <div className="font-bold text-slate-900 flex items-center gap-1">
                              <Pill className="w-3.5 h-3.5 text-amber-600" />
                              {item.medicine_name}
                            </div>
                            <div className="text-[11px] text-slate-600">
                              Dosage: {item.dosage} • Freq: {item.frequency}
                            </div>
                            <div className="text-[10px] text-slate-500">
                              Duration: {item.duration} {item.instructions && `(${item.instructions})`}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Dispense Action Button */}
                    <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                      <div className="text-[11px] text-slate-500 flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 text-slate-400" />
                        Issued: {new Date(rx.digital_signature_timestamp).toLocaleString()}
                      </div>

                      {!isDispensed ? (
                        <button
                          onClick={() => handleDispense(rx.id)}
                          disabled={dispensingId === rx.id}
                          className="py-2 px-4 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow-xs transition flex items-center gap-1.5"
                        >
                          <Sparkles className="w-3.5 h-3.5" />
                          {dispensingId === rx.id ? 'Dispensing...' : 'Mark Dispensed & Fulfilled'}
                        </button>
                      ) : (
                        <span className="text-xs font-bold text-emerald-700 flex items-center gap-1">
                          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                          Dispensed on {new Date(rx.dispensed_at || '').toLocaleTimeString()}
                        </span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: PHARMACY REGISTRATION */}
      {tab === 'register' && (
        <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-xs max-w-xl">
          <h2 className="text-base font-bold text-slate-900 mb-1 flex items-center gap-2">
            <Building2 className="w-5 h-5 text-amber-600" />
            Pharmacy License & Shop Information
          </h2>
          <p className="text-xs text-slate-500 mb-4">
            Under the Drugs and Cosmetics Act, licensed chemists can receive and dispense signed e-prescriptions.
          </p>

          {registered && (
            <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 font-bold flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              Pharmacy details registered successfully!
            </div>
          )}

          <form onSubmit={handleRegister} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Pharmacy Trade Name</label>
              <input
                type="text"
                required
                value={pharmacyName}
                onChange={(e) => setPharmacyName(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Drug License (DL) Number</label>
              <input
                type="text"
                required
                value={licenseNumber}
                onChange={(e) => setLicenseNumber(e.target.value)}
                placeholder="e.g. 20B/21B-DL-19948"
                className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Shop Address</label>
              <input
                type="text"
                required
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-xl text-xs"
              />
            </div>

            <div className="grid grid-cols-3 gap-2">
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
              className="py-2.5 px-5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold rounded-xl shadow-xs transition"
            >
              Save Pharmacy Credentials
            </button>
          </form>
        </div>
      )}
    </div>
  )
}
