# Requirements: Digital Healthcare Services Platform

**Defined:** 2026-09-10  
**Target Market:** Indian OPD Healthcare Marketplace & Clinical Operations  
**Architecture:** Python/FastAPI Modular Monolith + Node.js Real-Time Gateway + Redis Bridge  

---

## 1. Phase 1 MVP Requirements

### A. Patient-Facing Portal & Core Transactions (PAT)
- [ ] **PAT-01 (Auth & Profile)**: Patient account registration and login via Indian mobile number and SMS OTP, built on the Phase 01 unified Identity foundation. Single self-profile per login.
- [ ] **PAT-02 (Discovery & Search)**: Doctor search by medical specialty and city/locality with filters for consultation fee range, gender, and availability ("available today").
- [ ] **PAT-03 (Doctor Profile)**: Public doctor profile rendering bio, medical qualifications, specialty, clinic address, aggregate rating, and fixed fee per mode (in-person vs video).
- [ ] **PAT-04 (Slot Booking)**: Slot-based appointment booking for in-person and video visits with single fixed fee per doctor per consultation mode.
- [ ] **PAT-05 (Notifications)**: Automated booking confirmation notification and a single pre-appointment reminder notification (via SMS/Email).
- [ ] **PAT-06 (Health Records)**: Patient portal interface displaying historical consultations with list view and PDF download of issued digital prescriptions.
- [ ] **PAT-07 (Reviews & Feedback)**: Post-consultation rating prompt (1 to 5 stars) and optional written review submitted after an appointment transitions to `Completed`.
- [ ] **PAT-08 (Payments)**: Integrated payment gateway checkout (Razorpay) supporting Indian payment rails (UPI and debit/credit cards).
- [ ] **PAT-09 (Configurable Cancellation & Automated Refund Engine)**: Configurable policy engine (e.g., full refund if cancelled >= 2 hours before slot, non-refundable within 2 hours) with automated Razorpay refund initiation, appointment transition to `Cancelled`, and instant slot release.

### B. Doctor & Clinic Management Portal (DOC)
- [ ] **DOC-01 (Onboarding & Identity)**: Doctor registration utilizing the Phase 01 Identity system, with credential submission (medical council registration number, degree certificates) uploaded to S3/MinIO for administrative review.
- [ ] **DOC-02 (Single-Clinic Schedule)**: Single-clinic recurring weekly availability template configuration with configurable slot duration and inter-slot buffer times.
- [ ] **DOC-03 (Daily Queue Dashboard)**: Daily appointment queue management interface with explicit transition actions to mark an appointment `Completed` or `NoShow`.
- [ ] **DOC-04 (Digital Prescriptions)**: Structured digital prescription authoring (diagnosis, doctor clinical notes, medication items with name, dosage, frequency, duration, instructions) with static drug name autocomplete and asynchronous PDF generation.
- [ ] **DOC-05 (Visibility Toggles)**: Operational toggle switches for doctor listing (Online/Offline) and video consultation availability (Enabled/Disabled).

### C. Teleconsultation Engine (TEL)
- [ ] **TEL-01 (1:1 Video Session)**: Encrypted WebRTC video consultation strictly anchored to a `Confirmed` appointment record, accessible at scheduled appointment time via web browser or mobile client.
- [ ] **TEL-02 (In-Call Chat Relay)**: Text messaging thread tied to the consultation session for real-time exchange of notes, accessible during the consultation.
- [ ] **TEL-03 (Call Status Signaling)**: Simple real-time call status signaling (`waiting`, `connected`, `ended`) synchronizing doctor and patient clients.

### D. Platform Administration & Verification (ADM)
- [ ] **ADM-01 (Verification Queue)**: Admin review queue displaying submitted doctor credentials with actions to approve (`Verified`), reject (`Rejected` with mandatory reason text), or request info (`InfoRequested`).
- [ ] **ADM-02 (Admin Roles & RBAC)**: Role-Based Access Control enforcing two distinct internal roles: `super_admin` (full platform visibility) and `verification_reviewer` (credential verification queue only).
- [ ] **ADM-03 (Platform Dashboard)**: Operational governance telemetry displaying aggregate active doctors, total confirmed bookings, and gross transaction value (GTV).
- [ ] **ADM-04 (Review Moderation)**: Administrative moderation interface to inspect patient reviews with actions to approve, hide, or remove flagged content.

---

## 2. Cross-Cutting Hard Rules (Enforced & Verified per Phase)

- [ ] **RUL-01 (Zero Double-Booking)**: Strict concurrency guarantee preventing simultaneous booking of the same doctor slot. Enforced via Redis distributed lock (`SETNX`) during checkout and PostgreSQL exclusion/unique constraint on `(doctor_id, slot_start, slot_end)`.
- [ ] **RUL-02 (Real-Time Search Visibility Propagation)**: Doctor visibility toggle mutations (Online/Offline, Video Enabled/Disabled) and verification state changes must propagate immediately to search indexes and caches without stale delay.
- [ ] **RUL-03 (Atomic Slot + Payment Capture & Rollback)**: Slot reservation promotion to `Confirmed` and payment capture must be transactional. A payment failure or timeout immediately releases the slot lock; a captured payment guarantees confirmed slot allocation. Automated policy refunds execute with atomic slot release.
- [ ] **RUL-04 (Immutable Audit Logging)**: Every administrative action modifying a doctor's verification status, issuing a payment adjustment/refund, or moderating content must write an append-only, tamper-proof audit record containing admin ID, entity, diff, reason, timestamp, and IP.

---

## 3. Compliance Blocking Dependencies (Legal Counsel Sign-Off Gates)

- [ ] **CMP-01 (Telemedicine Restricted-Drug-Category Flag)**: India's Telemedicine Practice Guidelines prohibit remote prescription of Schedule X, narcotics, and habit-forming drugs, and differentiate first visits from follow-ups. The prescription module must implement a dynamic, database-configurable restriction flag. **Phase-blocking gate:** Production launch requires explicit sign-off from legal counsel on the restricted medication classification.
- [ ] **CMP-02 (DPDP Act Consent & Data Governance)**: Digital Personal Data Protection Act compliance requires a reusable, auditable consent service component (teleconsultation participation, medical data sharing, opt-in call recording) and field-level encryption for sensitive health data columns. **Phase-blocking gate:** Legal sign-off on consent capture language, retention windows, and privacy terms before public onboarding.

---

## 4. Explicitly Deferred to Phase 2 (Scope Fence — Do Not Implement in MVP)

1. **DEF-01**: Multi-clinic doctor support with merged calendar views and cross-clinic conflict resolution.
2. **DEF-02**: Linked dependent / family profiles under a single login account.
3. **DEF-03**: Live presence and queue wait-time broadcasting ("doctor running 10 minutes late").
4. **DEF-04**: WhatsApp Business API notification and reminder channels.
5. **DEF-05**: Full drug formulary with contraindication and drug-drug interaction warnings.
6. **DEF-06**: Doctor-facing performance analytics dashboards (earnings, demographic breakdown).
7. **DEF-07**: Multi-staff granular RBAC within a single clinic (receptionists, billing, nurses).
8. **DEF-08**: Multi-factor ranked search (proximity, rating, response time, and sponsored placement).
9. **DEF-09**: Full health records vault with arbitrary lab report upload and OCR structuring.
10. **DEF-10**: Follow-up consultation automated suggestions, subscriptions, and care packages.
11. **DEF-11**: Doctor-to-doctor clinical referrals and second opinion workflows.
12. **DEF-12**: Semi-automated scraping or API integration with NMC or State Medical Council registries.
13. **DEF-13**: Heuristic and automated fraud or duplicate-profile detection algorithms.
14. **DEF-14**: Full compliance self-service data export (`.zip`) and automated deletion pipeline.
15. **DEF-15**: Diagnostic lab test catalogue and home sample collection booking.
16. **DEF-16**: Corporate / enterprise health packages (B2B2C).
