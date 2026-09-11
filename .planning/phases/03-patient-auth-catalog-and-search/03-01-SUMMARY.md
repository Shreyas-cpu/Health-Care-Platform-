# Phase 03 Summary: Patient Identity Specialization, Catalog & Real-Time Search Sync

**Completed:** 2026-09-11  
**Subagent:** Codex CLI (`gpt-5.6-terra`)  
**Status:** 100% Completed & Verified (24 total tests passing across Phase 01, 02, & 03)  

---

## 1. What Was Delivered

### A. Patient Profile & Mobile OTP Authentication (PAT-01, CMP-02)
- **`Patient` Model (`backend/app/models/patient.py`):**
  - Attached directly to Phase 01 `User` record (`user_id` FK PK / 1:1 relation with `role='patient'`).
  - Stores `full_name`, `gender`, `date_of_birth`.
  - Primary self-profile only (linked dependents strictly deferred to Phase 2).
- **Patient Authentication API (`backend/app/api/v1/patient_auth.py`):**
  - `POST /api/v1/auth/patient/send-otp`: Dispatches 6-digit OTP code backed by Redis TTL cache via `IdentityService`.
  - `POST /api/v1/auth/patient/verify-otp`: Verifies OTP, creates/loads `User` (`role='patient'`), creates `Patient` profile, issues cryptographic JWT access token with role and user ID claims.
  - **DPDP Act Auditable Consent (`CMP-02`)**: Stores an immutable `ConsentRecord` row (`purpose='patient_registration_and_care'`, `consent_version='v1.0'`, client IP, and timestamp) in the active database transaction.
  - `GET /api/v1/auth/patient/me` & `PUT /api/v1/auth/patient/me` for profile reads and updates.

### B. Single Clinic Model & Doctor Catalog (DOC-05, PAT-02)
- **`Clinic` Model (`backend/app/models/clinic.py`):**
  - Single Clinic per doctor (`doctor_id` FK unique to `doctors.user_id`).
  - Stores clinic `name`, physical `address`, `city`, `locality`, `pincode`, and `contact_number`.
- **Doctor Consultation Fees & Attributes (`backend/app/models/doctor.py`):**
  - Added `in_person_fee: Decimal` (Numeric 10,2) and `video_fee: Decimal` (Numeric 10,2).
  - Added `gender` attribute and 1:1 `clinic` relation with `lazy="selectin"`.
- **Doctor Profile APIs (`backend/app/api/v1/doctor_profile.py`):**
  - `GET /api/v1/doctors/{doctor_id}`: Public doctor profile displaying bio, medical council registration, qualifications, specialty, clinic address, and consultation fees.
  - `POST /api/v1/doctors/me/clinic`: Doctor creates/updates single clinic information.
  - `POST /api/v1/doctors/me/toggle-listing`: Toggles online listing (strictly guarded: unverified doctors cannot go online) and invalidates Redis search cache immediately.
  - `POST /api/v1/doctors/me/toggle-video`: Toggles video availability and invalidates Redis search cache immediately.

### C. Real-Time Search Sync & Verification Gate (RUL-02, PAT-03)
- **Search Service (`backend/app/services/search_index.py`):**
  - Filter parameters supported: `specialty`, `locality`, `city`, `min_fee`, `max_fee`, `gender`, `video_available`.
  - **Hard Rule RUL-02 Gate**: Hard-coded filter strictly requiring `Doctor.verification_status == VerificationStatus.VERIFIED` AND `Doctor.listing_online == True`. Unverified or offline doctors are strictly excluded.
  - Redis Query Caching: Caches result sets under `cache:search:query:*` with 300s TTL.
  - Sub-200ms Invalidation: Invalidation hook `invalidate_search_cache()` deletes all `cache:search:*` keys immediately upon doctor status or visibility toggle.
- **Search API (`backend/app/api/v1/search.py`):**
  - `GET /api/v1/search/doctors` mounted in `backend/app/main.py`.

### D. Alembic Database Migration
- Generated and applied `a6f194cb9d21_phase_03_patient_clinic_and_fees.py` adding `patients` and `clinics` tables and fee/gender columns to `doctors`.

---

## 2. Requirements & Hard Rules Verified

| Requirement / Rule | Verification Method | Result |
|---|---|---|
| **PAT-01 (Patient OTP Auth)** | `test_patient_auth_and_dpdp_consent` | PASSED |
| **CMP-02 (DPDP Act Consent Capture)** | `test_patient_auth_and_dpdp_consent` | PASSED |
| **PAT-02 (Doctor Public Profile)** | `test_public_doctor_profile` | PASSED |
| **DOC-05 (Single Clinic Model & Fees)** | `test_public_doctor_profile` | PASSED |
| **PAT-03 (Search Filtering)** | `test_search_filters_and_rul02_verification_gate` | PASSED |
| **RUL-02 (Visibility & Verification Gate)** | `test_search_filters_and_rul02_verification_gate` | PASSED (Unverified/offline doctors strictly excluded) |
| **RUL-02 (Real-Time Search Invalidation)** | `test_realtime_visibility_toggle_invalidation` | PASSED (< 200ms cache purge) |
| **PAT-03 (Video Filter Invalidation)** | `test_video_enabled_toggle_invalidation` | PASSED |

---

## 3. Test Suite Results (`pytest -v`)

```text
tests/test_appointment_lifecycle.py::test_appointment_full_consultation_lifecycle PASSED [  4%]
tests/test_appointment_lifecycle.py::test_appointment_cancellation_lifecycle PASSED [  8%]
tests/test_appointment_lifecycle.py::test_appointment_reschedule_and_no_show PASSED [ 12%]
tests/test_appointment_lifecycle.py::test_illegal_state_transitions_raise_422 PASSED [ 16%]
tests/test_appointment_lifecycle.py::test_slot_double_booking_prevention_redis_and_db PASSED [ 20%]
tests/test_core_setup.py::test_settings_loaded PASSED                    [ 25%]
tests/test_core_setup.py::test_database_connectivity PASSED              [ 29%]
tests/test_core_setup.py::test_btree_gist_extension_present PASSED       [ 33%]
tests/test_core_setup.py::test_redis_distributed_lock PASSED             [ 37%]
tests/test_identity_foundation.py::test_user_roles PASSED                [ 41%]
tests/test_identity_foundation.py::test_jwt_issuance_and_decoding PASSED [ 45%]
tests/test_identity_foundation.py::test_otp_flow_with_dpdp_consent PASSED [ 50%]
tests/test_identity_foundation.py::test_admin_password_authentication PASSED [ 54%]
tests/test_search_sync.py::test_patient_auth_and_dpdp_consent PASSED     [ 58%]
tests/test_search_sync.py::test_search_filters_and_rul02_verification_gate PASSED [ 62%]
tests/test_search_sync.py::test_realtime_visibility_toggle_invalidation PASSED [ 66%]
tests/test_search_sync.py::test_video_enabled_toggle_invalidation PASSED [ 70%]
tests/test_search_sync.py::test_public_doctor_profile PASSED             [ 75%]
tests/test_verification_pipeline.py::test_doctor_onboarding_and_document_linking PASSED [ 79%]
tests/test_verification_pipeline.py::test_presigned_s3_url_generation PASSED [ 83%]
tests/test_verification_pipeline.py::test_full_6_state_verification_pipeline_with_immutable_audit PASSED [ 87%]
tests/test_verification_pipeline.py::test_rejection_requires_mandatory_reason PASSED [ 91%]
tests/test_verification_pipeline.py::test_unverified_doctor_cannot_go_online PASSED [ 95%]
tests/test_verification_pipeline.py::test_illegal_verification_transition_raises_422 PASSED [100%]

============================== 24 passed in 6.01s ==============================
```

---

## 4. Next Step

Phase 03 complete. Proceeding to:
- **Phase 04**: Scheduling, Atomic Slot Booking, Payments & Cancellation Engine (currently running via `cursor-cli`).
- **Phase 05**: Node.js Real-Time Gateway & Redis Pub/Sub Bridge (dequeued FIFO to `codex-cli`).
