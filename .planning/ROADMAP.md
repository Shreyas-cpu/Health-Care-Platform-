# Roadmap: Digital Healthcare Services Platform (MVP Loop)

## Overview & Sequencing Philosophy

This roadmap orchestrates the delivery of the exact MVP loop defined in PRD Section 3 for the Indian OPD marketplace. The implementation strictly adheres to the architectural split between the Python/FastAPI modular monolith and the Node.js real-time gateway, tied together by Redis Pub/Sub.

The sequence respects the critical dependencies among the three core state machines and foundational infrastructure:
1. **Unified Identity/Auth & The 8-State Appointment Lifecycle (Phase 01)** are built first as the architectural and transactional anchor of the entire platform. Every participant (doctor, patient, admin) needs a verified identity context, and every downstream operation (booking, payment, video, prescription) anchors to the appointment record.
2. **The 6-State Doctor Verification Pipeline (Phase 02)** establishes the trusted provider supply chain and audit foundation on top of doctor accounts before any provider can be searched.
3. **The 5-State Teleconsultation Session Model (Phase 06)** layers on top of confirmed appointments, driving synchronized transitions in the appointment lifecycle.
4. **The Cancellation & Refund Policy Engine (Phase 04)** is built right alongside booking and payment capture, ensuring automated policy-driven refunds operate atomically.
5. **Phase 09 Verification Split**: Hard rules and concurrency stress testing (RUL-01..04) are routed to `cursor` (`claude-opus-5-thinking-high`), while final docstring/lint/OpenAPI stabilization is routed to `devin` (`SWE-1.6 Slow`).

All 16 deferred items from PRD Section 3 are strictly fenced off from this roadmap.

---

## Phase Breakdown Summary

| Phase | Name | Focus & Boundaries | Delegate Subagent | Hard Rules & Compliance Gates |
|---|---|---|---|---|
| **Phase 01** | Core Architecture, Unified Identity & Appointment State Machine | PostgreSQL schema, SQLAlchemy async models, Unified User & Identity system (JWT issuance/verification, passwordless/OTP infrastructure), 8-state appointment machine, Redis distributed locking primitives, audit schema. | `cursor` (`composer-2.5` / `claude-opus-5-thinking-high`) | Foundation for **RUL-01**, **RUL-03**, **RUL-04**; **CMP-02** consent schema. |
| **Phase 02** | Doctor Onboarding & Verification Pipeline | Doctor profile attached to User identity, credential upload to S3/MinIO, 6-state verification pipeline, admin verification queue, immutable audit log writer. | `cursor` (`claude-opus-5-thinking-high` / `gpt-5.3-codex`) | **RUL-04** (Immutable Audit Logging); Verification gate for doctor visibility. |
| **Phase 03** | Patient Identity Specialization, Catalog & Real-Time Search Sync | Patient mobile OTP login (via Phase 01 Identity), doctor catalog profiles, Elasticsearch/OpenSearch indexing, real-time cache invalidation on visibility toggle. | `codex` (`gpt-5.6-terra`) | **RUL-02** (Real-Time Visibility Propagation); **CMP-02** (DPDP Consent Capture). |
| **Phase 04** | Scheduling, Atomic Slot Booking, Payments & Cancellation Engine | Single-clinic weekly schedule engine, slot generator, Razorpay checkout, distributed slot locking, atomic reservation promotion, and **Configurable Cancellation & Automated Refund Policy Engine**. | `cursor` (`composer-2.5` / `claude-opus-5-thinking-high`) | **RUL-01** (Zero Double-Booking); **RUL-03** (Atomic Slot + Payment Capture & Rollback). |
| **Phase 05** | Node.js Real-Time Gateway & Redis Pub/Sub Bridge | Dedicated Node.js service (NestJS/Express + WebSockets), Phase 01 JWT validation, Redis Pub/Sub adapter, room management, in-call chat relay. | `codex` (`gpt-5.6-terra`) | Architecture split isolation; Event routing between FastAPI and WebSockets. |
| **Phase 06** | Teleconsultation Engine & Session Lifecycle | 5-state session model, WebRTC LiveKit SFU integration, waiting room mechanics, call status signaling (`waiting`, `connected`, `ended`), chat persistence. | `cursor` (`claude-opus-5-thinking-high` / `composer-2.5`) | Dual state machine sync (Session <-> Appointment); **CMP-02** (Opt-in Recording Consent). |
| **Phase 07** | Clinical Ops Queue & Structured Digital Prescriptions | Doctor daily queue dashboard (complete/no-show actions), structured prescription builder, static drug autocomplete, Celery async PDF generation. | `codex` (`gpt-5.6-terra`) | **CMP-01** (Telemedicine Restricted-Drug Flag - Legal Sign-off Gate). |
| **Phase 08** | Admin Operations, Content Moderation & Audit Console | Super Admin & Reviewer RBAC, platform telemetry dashboard, post-visit rating/review submission, admin review moderation tooling. | `cursor` (`claude-opus-5-thinking-high` / `gpt-5.3-codex`) | **RUL-04** (Immutable Audit Logging on all admin mutations). |
| **Phase 09** | End-to-End MVP Golden Loop Verification & Hardening | **Plan 09-01**: Concurrency stress testing (RUL-01..04), race conditions, and e2e integration flow.<br>**Plan 09-02**: System hardening, docstring completeness, linting, and OpenAPI contract export. | **09-01**: `cursor` (`claude-opus-5-thinking-high`)<br>**09-02**: `devin` (`SWE-1.6 Slow`) | Complete audit of **RUL-01..04** and **CMP-01..02** across the end-to-end flow. |

---

## Phase Details

### Phase 01: Core Architecture, Unified Identity & Appointment State Machine Foundation
- **Goal**: Establish the foundational modular monolith backend, database schemas, the core **Unified Identity and Authentication system** (User model, role enum, JWT issuance/verification, OTP generation/validation engine), and the **8-state appointment lifecycle engine** with deterministic state transition rules.
- **Why First**: 
  1. Solves the auth sequencing gap: Doctor onboarding (Phase 02) and Patient login (Phase 03) both build on a shared, robust Identity infrastructure rather than reinventing ad-hoc sessions.
  2. Every marketplace transaction anchors to an appointment record.
- **State Machine (2A)**:
  `Requested` ➔ `Confirmed` ➔ `Rescheduled` ➔ `CheckedIn` ➔ `InConsultation` ➔ `Completed` ➔ `Cancelled` ➔ `NoShow`
- **Delegate Subagent**: `cursor` (`composer-2.5` / `claude-opus-5-thinking-high`)
  - *Rationale*: High cognitive rigor required. State transition correctness, JWT authentication infrastructure, Pydantic v2 schemas, and PostgreSQL exclusion constraint templates require formal verification.
- **Requirements Satisfied**: Core Identity foundation for PAT-01, DOC-01, ADM-02, plus PAT-04, DOC-03, TEL-01.
- **Hard Rules & Gates**:
  - Sets up the schema for **RUL-01** (PostgreSQL exclusion constraints) and **RUL-04** (immutable audit table).
  - Establishes the reusable consent record entity for **CMP-02** (DPDP Act).
- **Success Criteria**:
  1. Unified User and Auth engine issues signed JWTs with roles (`patient`, `doctor`, `verification_reviewer`, `super_admin`).
  2. Appointment model enforces all 8 valid states; illegal transitions raise strict 422 errors.
  3. Redis distributed lock utility is unit-tested under simulated concurrent requests.

---

### Phase 02: Doctor Onboarding & Verification Pipeline
- **Goal**: Implement doctor self-registration (anchored to Phase 01 User identity), credential document uploads to S3/MinIO, and the administrative 6-state verification workflow with mandatory reason tracking.
- **State Machine (2D)**:
  `Submitted` ➔ `UnderReview` ➔ `InfoRequested` ➔ `Verified` ➔ `Rejected` ➔ `Suspended`
- **Delegate Subagent**: `cursor` (`claude-opus-5-thinking-high` / `gpt-5.3-codex`)
  - *Rationale*: Critical trust boundary. Ensures unverified doctor profiles never leak into active status, and every reviewer mutation is immutably logged with mandatory reasoning.
- **Requirements Satisfied**: DOC-01, ADM-01.
- **Hard Rules to Verify**:
  - **RUL-04 (Immutable Audit Logging)**: Admin approval (`Verified`), rejection (`Rejected`), or suspension (`Suspended`) must write to `audit_logs` in the same database transaction.
- **Success Criteria**:
  1. Authenticated doctor can submit credentials and upload registration certificate and degree documents.
  2. Verification reviewer can transition application through all 6 states; rejection strictly requires a non-empty `reason` field.
  3. All status mutations generate immutable audit records.

---

### Phase 03: Patient Identity Specialization, Catalog & Real-Time Search Synchronization
- **Goal**: Implement patient mobile OTP login (specializing the Phase 01 Identity system), doctor public catalog profiles, and real-time synchronized doctor discovery search.
- **Delegate Subagent**: `codex` (`gpt-5.6-terra`)
  - *Rationale*: Rapid scaffolding of catalog endpoints, OpenSearch/PostgreSQL indexing, and Redis cache invalidation adapters.
- **Requirements Satisfied**: PAT-01, PAT-02, PAT-03, DOC-05.
- **Hard Rules to Verify**:
  - **RUL-02 (Real-Time Search Visibility Propagation)**: Only doctors in `Verified` state with `listing_online == true` appear in search. When a doctor toggles `listing_online` to `false` or disables video, search results and Redis profile caches must update immediately (< 200ms).
- **Compliance Blocking Dependencies**:
  - **CMP-02 (DPDP Act Patient Consent)**: Patient registration captures auditable consent record storing consent version, purpose, and timestamp.
- **Success Criteria**:
  1. Patient authenticates via mobile OTP and receives signed JWT; DPDP consent record is persisted.
  2. Search filters operate on specialty, locality, fee range, gender, and availability today.
  3. Toggling a doctor's visibility instantly reflects in search query responses.

---

### Phase 04: Scheduling, Atomic Slot Booking, Payments & Cancellation Engine
- **Goal**: Implement single-clinic recurring schedules, slot generation, distributed locking, Razorpay payment gateway integration, atomic reservation promotion, and the **Configurable Cancellation & Automated Refund Policy Engine**.
- **Cancellation & Refund Policy Architecture**:
  - Configurable policy rules (e.g. full refund if cancelled >= 2 hours before slot; non-refundable within 2 hours; doctor no-show automated refund).
  - Evaluates cancellation eligibility, initiates automated refund via Razorpay Refund API, transitions appointment to `Cancelled`, and immediately releases the reserved slot back to the catalog.
- **Delegate Subagent**: `cursor` (`composer-2.5` / `claude-opus-5-thinking-high`)
  - *Rationale*: Concurrency-critical financial transactions, distributed locking, and atomic state rollback.
- **Requirements Satisfied**: PAT-04, PAT-08, PAT-09, DOC-02.
- **Hard Rules to Verify**:
  - **RUL-01 (Zero Double-Booking)**: Concurrency stress tests with simultaneous requests for the exact same slot result in exactly 1 confirmation and 1 rejection.
  - **RUL-03 (Atomic Slot + Payment Capture & Rollback)**: Slot reservation promotion and Razorpay webhook capture execute in a single atomic transaction. Cancellations execute automated refund and atomic slot release.
- **Success Criteria**:
  1. Doctor configures recurring weekly schedule with configurable slot duration and buffers.
  2. Razorpay payment capture webhook atomically promotes slot to `Confirmed`.
  3. Automated cancellation engine executes policy-based refunds and slot releases.

---

### Phase 05: Node.js Real-Time Gateway & Redis Pub/Sub Event Bridge
- **Goal**: Build the dedicated Node.js microservice for high-concurrency WebSocket connections, handling signaling, status broadcasting, and in-call chat relay, bridged to FastAPI via Redis Pub/Sub.
- **Delegate Subagent**: `codex` (`gpt-5.6-terra`)
  - *Rationale*: Scaffolding NestJS/Express WebSocket gateways, Redis Pub/Sub subscriber loops, and client connection management.
- **Requirements Satisfied**: Architecture split (Section 4), TEL-02, TEL-03.
- **Success Criteria**:
  1. Node.js gateway validates Phase 01 JWTs during WebSocket handshake.
  2. Subscribes to Redis channels; propagates FastAPI appointment state changes to connected sockets in real time.
  3. In-call chat messages relay between doctor and patient sockets with sub-50ms latency.

---

### Phase 06: Teleconsultation Engine & 5-State Session Model
- **Goal**: Implement native 1:1 video consultation layered on top of confirmed appointments, orchestrating LiveKit WebRTC signaling, waiting room handoff, and chat persistence.
- **State Machine (2C)**:
  `Scheduled` ➔ `WaitingRoom` ➔ `Live` ➔ `Completed` ➔ `FollowUpScheduled`
- **Delegate Subagent**: `cursor` (`claude-opus-5-thinking-high` / `composer-2.5`)
  - *Rationale*: Dual-state machine synchronization between Teleconsultation (2C) and Appointment (2A), timeout fail-safes, and LiveKit token generation.
- **Requirements Satisfied**: TEL-01, TEL-02, TEL-03.
- **Compliance Gates**:
  - **CMP-02**: Explicit dual-party opt-in consent captured before session recording can be initialized.
- **Success Criteria**:
  1. Confirmed appointment generates valid LiveKit video room tokens at scheduled time.
  2. Patient entry into waiting room transitions appointment to `CheckedIn`.
  3. Doctor session start transitions both parties to `InConsultation` simultaneously.
  4. Abandoned sessions trigger timeout rules offering reschedule/refund per Phase 04 cancellation policy.

---

### Phase 07: Clinical Operations Queue & Structured Digital Prescription Engine
- **Goal**: Implement the doctor's daily OPD queue dashboard and structured digital prescription creation engine with static drug autocomplete and Celery PDF compilation.
- **Delegate Subagent**: `codex` (`gpt-5.6-terra`) with `cursor` review on compliance rules
- **Requirements Satisfied**: DOC-03, DOC-04, PAT-06.
- **Compliance Blocking Dependency**:
  - **CMP-01 (Telemedicine Restricted-Drug-Category Flag)**:
    - Drug table contains `is_telemedicine_restricted: boolean`. For video appointments, the prescription UI blocks selection of restricted medications.
    - *Phase Gate*: Written sign-off from legal/compliance counsel confirming the restricted drug list prior to production deployment.
- **Success Criteria**:
  1. Doctor daily queue renders all appointments for the date with live status pills.
  2. Completed appointments unlock prescription authoring with static drug autocomplete.
  3. Celery worker compiles vector PDF stored in S3 and linked to patient health records.

---

### Phase 08: Admin Operations, Content Moderation & Immutable Audit Logging
- **Goal**: Build administrative console for platform telemetry, role-based access control, post-visit rating/review flow, and content moderation with immutable audit trails.
- **Delegate Subagent**: `cursor` (`claude-opus-5-thinking-high` / `gpt-5.3-codex`)
  - *Rationale*: Security-sensitive administrative boundaries, strict RBAC, and tamper-proof audit log integrity.
- **Requirements Satisfied**: ADM-02, ADM-03, ADM-04, PAT-07, PAT-05.
- **Hard Rules to Verify**:
  - **RUL-04 (Immutable Audit Logging)**: Every admin mutation (doctor verification status, review hiding/removal, manual refund) writes an immutable audit record.
- **Success Criteria**:
  1. `super_admin` accesses platform telemetry; `verification_reviewer` is restricted to verification queues.
  2. Patient submits 1-5 star rating and text review after appointment is `Completed`.
  3. Admin review moderation creates immutable audit log records.

---

### Phase 09: End-to-End MVP Golden Loop Verification & Hardening (Split Execution)

#### Plan 09-01: Concurrency Stress-Testing, Race Conditions & Hard Rules Verification
- **Delegate Subagent**: `cursor` (`claude-opus-5-thinking-high`)
  - *Rationale*: High-stakes concurrency and transactional integrity. The same subagent that built Phase 04 and Phase 02 verifies RUL-01..04 under race conditions across modules.
- **Scope**:
  - Concurrency stress test: 100 simultaneous booking attempts for same slot (RUL-01).
  - Search visibility propagation under continuous query load (RUL-02).
  - Atomic slot reservation, payment capture, and rollback on gateway timeout (RUL-03).
  - Audit log completeness: 100% of admin mutations written immutably (RUL-04).
  - Full automated golden loop execution: Patient Reg ➔ Search ➔ Book & Pay ➔ Doctor Queue ➔ Video Consult ➔ Prescription PDF ➔ Review ➔ Admin Audit.

#### Plan 09-02: System Hardening, Docstrings, Linting & Contract Export
- **Delegate Subagent**: `devin` (`SWE-1.6 Slow`)
  - *Rationale*: Devin excels at thorough code cleanup passes, ensuring docstring coverage, standardizing formatting (Black/Ruff/Prettier), and validating exported OpenAPI contracts.
- **Scope**:
  - Codebase cleanup and style formatting across backend and real-time gateway.
  - Complete docstring coverage on all public endpoints and state machines.
  - Export and schema validation of `docs/OPENAPI_SPEC.json`.
  - Compile final `docs/COMPLIANCE_SIGN_OFF.md` for legal sign-off gates (CMP-01, CMP-02).
  - Audit confirming 100% absence of all 16 Phase 2 deferred features.
