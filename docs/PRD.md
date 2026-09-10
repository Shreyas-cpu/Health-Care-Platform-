PROJECT REQUIREMENTS AND TECHNICAL ARCHITECTURE DOCUMENT​
DIGITAL HEALTHCARE SERVICES PLATFORM
DOCUMENT CONTROL​
Prepared For: Project Manager and AI Development Agent​
Document Type: Combined Product Requirements Document and Technical Architecture
Blueprint​
Version: 1.0​
Date: September 09, 2026
READING NOTE​
This document serves two readers at once. Passages describing business logic, user value,
and scope decisions are written for the Project Manager. Passages describing entities,
states, data flow, and technology choices are written as literal specifications for the AI coding
agent. Where a business rule has a direct technical consequence, both are stated together
so nothing is lost in translation between the two roles. Throughout this document the system
is referred to simply as "the Platform" — substitute your chosen brand name everywhere this
appears.
1.​ FINAL DEVELOPMENT GOAL
The Platform is a two-sided digital healthcare marketplace and clinical operations system. It
connects patients seeking medical care with verified doctors, clinics, and diagnostic
providers, and gives those providers the operational tools to run their practice through the
same system. The end state is a single production platform in which the following is true
without manual intervention:
A patient can discover a suitable doctor, book a confirmed appointment (in person or by
video), attend the consultation, receive a digital prescription, pay for the service, and retrieve
every past interaction from one continuous account history.
A doctor or clinic administrator can manage their schedule, control their visibility to patients,
run their daily patient queue, issue digital prescriptions, and see their own performance,
entirely inside the Platform, without phone calls or spreadsheets.
Teleconsultation is a native, first-class appointment type, not an add-on. Video, chat, and
real-time appointment status all live inside the same booking and record system as in-person
visits.
Platform administrators can verify that every doctor on the Platform is who they claim to be
and holds a valid medical qualification, and can monitor the health, trust, and safety of the
marketplace as it scales.

END STATE CAPABILITIES
1. Multi-channel doctor and clinic discovery (specialty, symptom, location, language, fee
range)

2. Real-time slot-based appointment booking with no double-booking, for both in-person and
video visits
3. Native video and chat teleconsultation tied to the appointment record
4. Structured digital prescriptions that are stored permanently against the patient's account
5. Integrated payments for consultation fees, with cancellation and refund handling
6. Doctor and clinic self-service practice management (schedule, visibility, queue,
prescriptions, basic analytics)
7. Administrative credential verification pipeline for every doctor and clinic before they go live
8. Platform-wide oversight tooling: analytics, content moderation, audit logging, role-based
admin access

EXPLICITLY OUT OF SCOPE FOR THIS BUILD
To keep the coding agent's boundaries unambiguous, the following are not part of this
system and should not be built unless a future revision of this document says otherwise:
1. Insurance claim submission, adjudication, or cashless-approval workflows
2. Pharmacy order fulfillment or medicine delivery logistics (the Platform may reference a
prescription; it does not fulfill it)
3. Inpatient or hospital admission (IPD) management — this is an outpatient (OPD)
consultation platform
4. Diagnostic lab equipment integration or automated lab result interpretation (manual report
upload only, see Phase 2 for lab booking)
5. Multi-country localization — the initial build targets the Indian market and its regulatory
context only
6. Direct, automated integration with the National Medical Commission or State Medical
Council registries (treated as a manual-verification workflow at this stage; see Section 2D)

2. DEEP RESEARCH AND FUNCTIONALITY ANALYSIS
Each subsection below describes the business purpose first, then the user flow, then the
technical state model the coding agent should implement.
A. THE PATIENT PORTAL
Business purpose
The Patient Portal is the demand side of the marketplace. Its job is to convert a person with
a medical need into a confirmed, paid appointment as quickly and with as much
trust-building context as possible, and then to become the permanent home for that person's
consultation history.
Search and Discovery
Patients search in two primary ways: by specialty or symptom ("dermatologist," "fever and
cough") and by proximity (city, locality, or pincode). Search results are filterable by
consultation fee range, gender of doctor, years of experience, language spoken, and
availability ("available today," "available for video now"). Each result links to a doctor profile
page showing qualifications, registered specialty, years of experience, clinic locations and

fees per clinic, aggregate rating and review count, and a count of patients previously
consulted. Search ranking should combine relevance (specialty/symptom match), proximity,
rating, and current availability; sponsored or promoted placement is a Phase 2 concern and
should be architected as a pluggable ranking weight, not hardcoded into the base query.
Booking Flow
The flow is: select doctor, select a clinic and consultation mode (in-person or video) if the
doctor offers more than one, select an open slot from a real-time calendar, confirm which
patient profile the booking is for (self or a linked dependent), and confirm the booking.
Depending on the clinic's own policy, confirmation may require upfront payment or may
simply reserve the slot. On confirmation the patient receives a booking confirmation and is
queued for automated reminders.
Appointment Lifecycle (state model for the coding agent)
Every appointment is a single record moving through a defined state machine:
1. Requested — slot selected, payment (if required) not yet captured
2. Confirmed — slot locked, payment captured or policy satisfied
3. Rescheduled — patient or doctor moved the slot; links back to the original request
4. CheckedIn — patient has arrived (in-person) or entered the waiting room (video)
5. InConsultation — doctor has started the session
6. Completed — consultation finished, prescription may now be attached
7. Cancelled — terminated before consultation, by either party, subject to a cancellation
policy
8. NoShow — confirmed slot passed with no check-in
This state machine is shared by both consultation modes; only the
CheckedIn-to-InConsultation transition mechanics differ (front-desk action for in-person,
waiting-room-to-live handoff for video, detailed in Section 2C).
Health Records and History
Every completed appointment produces a permanent record in the patient's account: the
digital prescription, any doctor notes visible to the patient, and any files the patient uploaded
before the visit (lab reports, prior prescriptions). A single login can hold multiple linked
patient profiles (self plus dependents such as children or parents), and each profile has its
own independent history.
Payments and Reviews
Consultation fees are captured through an integrated payment gateway at the point the
booking policy requires it. Cancellations and refunds follow a configurable policy engine (for
example, free cancellation up to two hours before the slot). After a Completed appointment,
the patient is prompted once for a star rating and optional written review, which becomes
part of the doctor's public profile after passing moderation (Section 2D).
Notifications
Booking confirmation, a reminder at a fixed interval before the appointment, reschedule or
cancellation alerts, and "prescription ready" notifications are sent through whichever
channels are enabled for the deployment (push, SMS, email; WhatsApp is a Phase 2
channel, see Section 3).

B. THE DOCTOR AND CLINIC MANAGEMENT PORTAL
Business purpose
This is the supply side of the marketplace. Its job is to let a doctor or clinic run their entire
outpatient practice — visibility, scheduling, patient flow, and documentation — without
needing any tool outside the Platform, because every hour spent outside the Platform is an
hour that generates no bookings for it.
Onboarding and Profile
A doctor registers with identity details, medical qualifications, registration number, specialty,
years of experience, and the clinic(s) they practice from, including a fee per clinic and per
consultation mode. No doctor profile becomes publicly searchable until it clears the
verification pipeline described in Section 2D.
Schedule Management
A doctor (or clinic admin, for a multi-doctor clinic) defines a recurring weekly availability
template per clinic and per mode, with a configurable slot duration and buffer time between
slots. Specific dates can be blocked out for leave. Where a doctor practices across multiple
clinics, the system must merge all clinic calendars into one conflict-free view — a doctor
cannot be double-booked across two locations at the same time, even though patients book
against a specific clinic. This cross-clinic conflict check is a hard business rule, not a
display-layer convenience.
Profile Visibility Controls
A doctor can toggle whether they are currently accepting new patients, pause their listing
entirely, and independently toggle whether video consultations are currently offered. These
toggles must take effect in patient search results in real time — if a doctor turns off video
consultations mid-day, that doctor should immediately stop appearing in "available for video
now" search filters. This is a direct real-time consistency requirement between the
practice-management side and the discovery side of the Platform.
Queue and Check-in Management
For physical clinics, front-desk staff (a distinct role from the doctor) can mark a patient as
arrived, reorder the day's queue to accommodate walk-ins alongside scheduled bookings,
and see the live state of every appointment on the day's list.
Digital Prescriptions
At or after the consultation, the doctor completes a structured prescription: diagnosis and
notes, and one or more medications, each with dosage, frequency, duration, and
instructions, drawn from an autocomplete-assisted drug list (a full formulary with interaction
checking is a Phase 2 enhancement; MVP needs a simple name-and-instructions entry with
autocomplete against a static drug name list). The finished prescription is rendered to a
shareable, downloadable document, digitally signed or stamped by the doctor, and attached
permanently to the patient's record. Prescriptions issued after a teleconsultation are subject
to India's telemedicine prescribing rules, which restrict which categories of medication may
be prescribed remotely and on a first consultation versus a follow-up — the prescription
module should support a configurable restricted-drug-category flag so this rule can be

enforced or updated without a code change, and the specific current restrictions should be
confirmed with legal or compliance counsel before launch rather than hardcoded from this
document.
Clinic Administration and Analytics
A clinic-admin role manages multiple doctors and front-desk staff under one clinic entity, with
visibility into clinic-level booking volume and revenue. Doctor-facing performance analytics
(appointment volume, revenue, patient demographics, rating trend) are listed under Phase 2
in Section 3, since they are valuable but not required for the core booking loop to function.

C. THE TELECONSULTATION ENGINE
Business purpose
This module is what turns "book an appointment" into "get seen by a doctor" without either
party leaving the app. It is the most real-time-intensive part of the Platform and is the primary
reason this document recommends splitting real-time workloads onto a dedicated
concurrency-optimized service (see Section 4).
Video
A video session is always tied to a specific Confirmed appointment record, never a
freestanding call. At the scheduled time (or, for on-demand doctors, once the doctor signals
availability), the patient enters a waiting room state and the doctor's dashboard shows the
patient as ready. The doctor initiates the session start, which transitions the appointment to
InConsultation for both parties simultaneously. The join experience must work both from
inside the Platform's app and from a web link delivered by SMS or notification, for patients
without the app installed. The session supports screen or file sharing for reviewing reports
live, and should degrade gracefully (lower video quality before dropping the call entirely) on
poor connections, with automatic reconnection if a participant briefly loses connectivity.
Session recording is opt-in only and requires explicit consent capture from both parties
before it can start, given the sensitivity of medical consultations.
Chat
Each appointment also has an associated chat thread, usable before the visit (for the patient
to share context or files) and after it (for short follow-up questions within a bounded post-visit
window). Chat messages and any attached files become part of the patient's permanent
record for that appointment, the same as the prescription.
Real-Time Status
Three real-time signals are required for this module to feel live rather than static: the doctor's
current session state ("in consultation," "running late," "available now") visible to the relevant
patients; a live queue position for patients waiting on a given day's schedule; and a presence
indicator (online, offline, busy) for doctors who offer on-demand teleconsultation outside
pre-booked slots. All three are pushed to connected clients the moment the underlying state
changes in the core system — this is the "live appointment routing" requirement referenced
in Section 4's technology choices.
Session State Model (for the coding agent)

A teleconsultation session, layered on top of the appointment lifecycle in Section 2A, moves
through: Scheduled, WaitingRoom (patient present, doctor not yet joined), Live (both
present), Completed, and optionally FollowUpScheduled if the doctor books a next visit
directly from the session. Transitions are driven by a mix of explicit user action (doctor
clicking "start") and time-based rules (a session waiting more than a defined timeout with no
doctor join should alert the doctor and, past a second timeout, offer the patient a reschedule
or refund path per the cancellation policy).

D. PLATFORM ADMINISTRATION AND VERIFICATION
Business purpose
Trust is the product. A patient booking a doctor through the Platform is trusting that the
Platform has already checked that the doctor is real and qualified. This module exists to
make that trust true, and to keep the marketplace healthy as it grows past the point where
every doctor can be personally known to the platform operator.
Doctor and Clinic Verification Pipeline
When a doctor or clinic submits an onboarding application, they upload supporting
documents: medical council registration certificate, degree certificates, and, for a clinic entity,
business registration and tax identification documents. An automated pre-check (document
presence, basic OCR-based data extraction to catch obviously mismatched or incomplete
submissions) feeds a manual reviewer queue, since a fully open, machine-checkable
national registry of medical council registrations is not consistently available in India today —
this pipeline should be designed as manual-review-with-audit-trail by default, with automated
cross-checking treated as a Phase 2 enhancement to be added if and when a reliable
registry integration becomes available, not assumed as available at MVP.
Verification States (for the coding agent)
1. Submitted — application received, documents attached
2. UnderReview — assigned to a reviewer
3. InfoRequested — reviewer needs additional documentation from the applicant
4. Verified — approved, profile becomes eligible to go live in search
5. Rejected — application declined, with a reason recorded
6. Suspended — a previously Verified doctor or clinic has been taken offline for a
trust-and-safety reason after launch
Ongoing Trust and Safety
Administrators handle patient complaints against a doctor or listing, moderate submitted
reviews before or after they go public (to catch abusive content or suspected fake reviews),
and can suspend a previously verified doctor pending investigation. Duplicate or fraudulent
profile detection is listed under Phase 2, since it depends on having enough real profile
volume to build detection rules against.
System Oversight
Internal staff need platform-wide dashboards (total bookings, active doctors and patients,
teleconsultation volume, gross transaction value), content management tools for the
specialty taxonomy and city or locality master data used throughout search, and role-based

access control so that a support agent, a verification reviewer, and a super-admin each see
only what their role requires. Every administrative action that changes a doctor's status, a
payment, or a piece of published content must write an immutable audit log entry — this is
both an operational requirement and a compliance requirement.
Compliance
Two regulatory contexts should shape this module's design from the start, though the exact
current requirements should be confirmed with legal counsel rather than taken as final from
this document: India's Digital Personal Data Protection Act, which governs how patient
consent, data retention, and data deletion requests must be handled, and the Telemedicine
Practice Guidelines referenced in Section 2B, which govern teleconsultation consent capture
and prescribing limits. The consent capture flow (for teleconsultation participation, for data
sharing, and for any session recording) should be built as a reusable, auditable component
rather than a one-off checkbox, since it will be referenced by more than one module.

3. DEVELOPMENT ROADMAP AND FEATURE BREAKDOWN
The MVP is scoped to prove exactly one thing end to end: a patient can find a real, verified
doctor, book them, be seen (in person or by video), receive a prescription, pay, and rate the
experience. Everything not required for that loop is deferred.
MVP — PATIENT-FACING FEATURES
1. Account registration and login via mobile number and OTP
2. Doctor search by specialty and city or locality, with basic filters (fee, gender, availability)
3. Doctor profile page (bio, qualifications, fee, clinic address, aggregate rating)
4. Slot-based appointment booking, both in-person and video, single fixed fee per doctor per
mode
5. Booking confirmation plus a single reminder notification before the appointment
6. Basic health record view: list and download of past prescriptions
7. Post-visit star rating and text review
8. Integrated payment capture for the consultation fee (UPI and card support via a payment
gateway suited to the Indian market, such as Razorpay)

MVP — DOCTOR AND CLINIC FEATURES
1. Doctor self-registration with document upload for manual verification
2. Single-clinic recurring weekly schedule setup
3. Daily appointment queue dashboard with mark-complete and mark-no-show actions
4. Structured digital prescription creation with PDF generation
5. Online and offline listing toggle

MVP — TELECONSULTATION
1. One-to-one video call tied to a Confirmed appointment, joinable at the scheduled time
2. Basic in-call text chat

3. Simple call status indicator (waiting, connected, ended) — full live-queue and presence
broadcasting is deferred to Phase 2

MVP — ADMINISTRATION
1. Manual document review queue with approve or reject and a reason field
2. Two admin roles: super admin and verification reviewer
3. Basic platform dashboard: total doctors, total bookings, total revenue
4. Manual review moderation (hide or remove a flagged review)

EXPLICITLY DEFERRED TO PHASE 2
1. Multi-clinic doctor support with merged calendars
2. Linked dependent or family profiles under one login
3. Live presence and queue-position broadcasting ("doctor running 10 minutes late")
4. WhatsApp Business API notifications and reminders
5. Full drug formulary with autocomplete and interaction warnings
6. Doctor-facing analytics dashboards
7. Multi-staff, granular role-based access within a single clinic
8. Ranked search combining proximity, rating, response time, and sponsored placement
9. Full health records vault with lab report upload and OCR structuring
10. Follow-up consultation suggestions and subscription or care-plan packages
11. Doctor-to-doctor referral and second-opinion workflow
12. Semi-automated medical council registration cross-checking
13. Fraud and duplicate-profile detection
14. Full compliance reporting suite, including automated data export and deletion requests
15. Diagnostic lab test booking as an adjacent marketplace vertical
16. Corporate or enterprise health package offerings (B2B2C)

4. TECHNOLOGY STACK AND OPERATIONS
Backend Architecture​
The core backend is a modular monolith at MVP stage, built primarily in Python with
FastAPI, organized internally into clearly bounded modules (Identity and Auth, Catalog,
Scheduling and Booking, Consultation, Prescription and Records, Payments, Notifications,
Admin and Verification, Reviews) so that any module can be extracted into its own
microservice later without a rewrite. FastAPI is recommended because it is async-native,
generates OpenAPI schemas automatically (useful both as PM-readable API documentation
and as a machine-readable contract for the coding agent), and its Pydantic-based typing
enforces the exact data contracts described in Section 2, such as the appointment and
verification state machines, at the framework level rather than by convention.
A dedicated Node.js service, using NestJS or Express, should be split out specifically for the
workloads that need to hold many concurrent, long-lived connections: the WebSocket
signaling server for teleconsultation (exchanging connection setup information and
managing call rooms), the live presence and queue-status broadcaster described in Section

2C, and the chat message relay. This separation exists because Node's event-loop model
and WebSocket ecosystem are a better fit for thousands of simultaneously open sockets
than a request-response framework like FastAPI, and isolating that traffic keeps the core
booking and records service simple and easy to reason about.
WebSocket clients authenticate with a short-lived token issued by the FastAPI identity
module, then connect to the Node.js real-time gateway. The gateway uses Redis Pub/Sub
internally so that multiple gateway instances stay in sync, and so that a state change made
in the core FastAPI service (for example, a doctor marking an appointment InConsultation)
can be published to Redis and immediately fanned out over WebSocket to every relevant
connected client — this is the mechanism behind "live appointment routing."
For the video layer itself, the recommendation is to use a managed or self-hosted Selective
Forwarding Unit rather than building a custom media server — LiveKit as an open-source,
self-hostable option, or Twilio Video or Agora as fully managed alternatives. The Node.js
gateway only ever handles call signaling, never media relay.
Background and asynchronous work (reminder dispatch, PDF prescription generation, report
processing, notification fan-out) runs through Celery, backed by Redis or RabbitMQ as the
message broker.
Frontend​
The patient-facing web experience and the doctor and clinic management portal are built in
React with Next.js, chosen specifically because doctor profile and specialty pages need to
be indexable and shareable for organic search traffic, which is a large part of how a platform
like this actually acquires patients. The patient mobile app is React Native, sharing
design-system and business-logic patterns with the web app where practical, and is where
deep links from SMS or notifications and the native video SDK integrate most naturally. The
internal admin and verification console can be a simpler React single-page application built
with Vite, since it has no public-facing SEO requirement and should prioritize development
speed over that concern. Server-state (API data) should be managed with React Query,
paired with a lightweight client-state library such as Zustand rather than a heavier
state-management framework.
Databases​
PostgreSQL is the system of record for every core transactional entity: users, doctors,
clinics, appointments, prescriptions, and payments. These entities require strong relational
integrity and transactional guarantees — a slot booking and its associated payment must
succeed or fail together, and appointment-to-prescription-to-patient relationships must be
enforced at the database level, not just in application code. Read replicas can absorb search
and browse traffic as the Platform scales.
A document store, either MongoDB or PostgreSQL's own JSONB columns depending on
team familiarity, holds schema-flexible content: chat message logs, the richer free-text
sections of a doctor's profile, audit and event logs, and denormalized doctor-listing
documents optimized for fast reads.

A dedicated search index, Elasticsearch or OpenSearch, powers the Patient Portal's doctor
discovery search, since faceted, location-aware, ranked search at scale is beyond what
Postgres full-text search comfortably handles.
Redis serves three distinct roles in this architecture: a cache for hot read paths like doctor
profiles and slot availability, the Pub/Sub backbone connecting the FastAPI service to the
Node.js real-time gateway, and a distributed lock used specifically to prevent two patients
from booking the same slot at the same instant.
Object storage, using AWS S3 or a self-hosted S3-compatible store such as MinIO, holds
prescription PDFs, patient-uploaded reports, doctor verification documents, and profile
photography.
Cloud and DevOps​
AWS is the recommended cloud provider, chosen for the maturity of its managed services
against this specific architecture: RDS for Postgres, ElastiCache for Redis, S3 for object
storage, and SES or SNS for notification delivery; GCP is an equally valid alternative if the
team has existing expertise there.
All services are containerized with Docker. At MVP scale, AWS ECS Fargate is sufficient and
keeps operational overhead low for a small team; once the system has genuinely split into
the FastAPI service, the Node.js real-time gateway, and background workers as separate
deployable units, migrating to Kubernetes (EKS) becomes worthwhile.
CI and CD run through GitHub Actions: lint, type-check, and test on every pull request, build
and push container images on merge, and deploy through blue/green or canary releases.
Terraform manages all cloud infrastructure as code, so that development, staging, and
production environments stay reproducible and so that the coding agent has a single
declarative source of truth for infrastructure changes rather than manual console
configuration.
Observability includes structured JSON logging shipped to a central store, distributed tracing
via OpenTelemetry (essential once a single teleconsultation session's failure needs to be
traced across both the FastAPI and Node.js services), and metrics and alerting through
Prometheus and Grafana.
Security practices include secrets management through AWS Secrets Manager, encryption
at rest and in transit by default across every data store, field-level encryption for the most
sensitive health data columns, a regular penetration testing cadence, and hosting in an AWS
India region (ap-south-1) to align with data-residency expectations under India's data
protection law and with the Platform's own target market. Development, staging, and
production environments should be strictly separated, with feature flags used to ship Phase
2 functionality without destabilizing the MVP core loop.

