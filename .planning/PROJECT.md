# Digital Healthcare Services Platform

## What This Is
A production-ready, two-sided digital healthcare marketplace and clinical operations platform tailored for the Indian outpatient department (OPD) market. The platform connects patients seeking medical care with verified doctors and clinics, while providing medical practitioners with full operational tools to manage their practice, schedule, live queues, teleconsultations, and structured digital prescriptions without manual friction or external spreadsheets.

## Core Value (MVP Golden Loop)
To validate and deliver the single complete clinical loop end-to-end:
A patient finds a real, verified doctor -> books a confirmed slot (in-person or video) -> attends the consultation -> receives a structured digital prescription -> pays the consultation fee -> rates the visit.

## Primary Personas
1. **Patient**: Discovers verified doctors by specialty/locality, books confirmed slots, attends in-person or native 1:1 video consultations, receives and downloads permanent digital prescriptions, pays via UPI/Cards, and provides post-visit reviews.
2. **Doctor / Clinic Provider**: Self-onboards with medical council credentials, configures weekly recurring schedules and consultation fees per mode, manages daily operational patient queues, conducts video sessions, and issues structured digital prescriptions.
3. **Platform Administrator**:
   - `super_admin`: Platform-wide governance, transaction telemetry, audit logs, content management.
   - `verification_reviewer`: Inspects doctor credentials (degrees, medical council registrations) and approves or rejects with mandatory reason codes.

## System Architecture Summary
Reflecting PRD Section 4:
- **Core Backend (Python / FastAPI Modular Monolith)**:
  - Modules: `Identity & Auth`, `Catalog`, `Scheduling & Booking`, `Consultation`, `Prescription & Records`, `Payments`, `Notifications`, `Admin & Verification`, `Reviews`.
  - Pydantic v2 data contracts enforcing state machine integrity at framework level.
  - SQLAlchemy 2.0 async ORM with PostgreSQL system of record.
  - Celery workers backed by Redis for async tasks (PDF prescription generation, reminders).
- **Real-Time Gateway (Node.js / NestJS or Express)**:
  - Dedicated microservice handling long-lived WebSocket connections.
  - WebRTC signaling (SDP offer/answer, ICE candidates) for 1:1 teleconsultation; coordinates call rooms via LiveKit SFU (no media relay).
  - In-call chat relay and simple call status indicators (`waiting`, `connected`, `ended`).
- **Data & Caching Backbone**:
  - **PostgreSQL**: System of record for users, doctors, clinics, appointments, payments, prescriptions. ACID transactions and exclusion constraints.
  - **Redis**: Distributed locks (`lock:doctor:{id}:slot:{timestamp}`), hot profile caching, and Redis Pub/Sub bridge connecting FastAPI events to Node.js WebSocket subscribers ("live appointment routing").
  - **Elasticsearch / OpenSearch**: Faceted doctor discovery index synchronized in real time with doctor verification and visibility toggles.
  - **S3 / MinIO**: Object store for doctor verification credentials and generated prescription PDFs.
- **Frontend Applications**:
  - **Patient Web & Doctor Portal**: React / Next.js (SSR/SSG for SEO on doctor profiles, React Query, Tailwind CSS).
  - **Admin & Verification Console**: Vite + React SPA (rapid operational dashboard).
  - **Patient Mobile**: React Native with shared design tokens and deep-linking support.

## Three Backbone State Machines
1. **8-State Appointment Lifecycle (Section 2A)**:
   `Requested` -> `Confirmed` -> `Rescheduled` -> `CheckedIn` -> `InConsultation` -> `Completed` -> `Cancelled` -> `NoShow`
2. **5-State Teleconsultation Session Model (Section 2C)**:
   `Scheduled` -> `WaitingRoom` -> `Live` -> `Completed` -> `FollowUpScheduled`
3. **6-State Doctor Verification Pipeline (Section 2D)**:
   `Submitted` -> `UnderReview` -> `InfoRequested` -> `Verified` -> `Rejected` -> `Suspended`

## Scope Boundaries
- **Strictly In-Scope (Phase 1 MVP)**:
  - Mobile OTP auth for patients; Doctor self-registration & document upload.
  - Basic doctor search & filtering (specialty, locality, fee, gender, availability).
  - Slot booking (in-person and video) with single fixed fee per doctor per mode.
  - 1:1 Video consultation with LiveKit signaling, in-call chat, simple status.
  - Structured digital prescription creation + PDF generation.
  - Razorpay payment capture (UPI and card).
  - Post-visit star rating and text review with admin moderation.
  - Manual document verification queue with approve/reject and reasons.
  - Platform dashboard: total doctors, total bookings, total revenue.
  - 2 Admin roles: `super_admin` and `verification_reviewer`.
- **Strictly Deferred to Phase 2 (Out of Scope)**:
  - Multi-clinic merged calendars; Linked family/dependent profiles; Live presence & queue wait broadcasting ("doctor running 10 mins late"); WhatsApp Business API; Full drug formulary with interaction checks; Doctor-facing analytics; Multi-staff clinic RBAC; Ranked/sponsored search; Lab test booking; Full health records vault & OCR; Subscriptions/care plans; Doctor referrals; Automated registry integration; Fraud detection; Full compliance reporting suite; Corporate/B2B2C packages.
