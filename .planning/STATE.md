# Project State: Digital Healthcare Services Platform

**Milestone:** Milestone 1 — MVP Core Loop  
**Current Phase:** Phase 01: Core Architecture, Unified Identity & Appointment State Machine Foundation  
**Status:** Planning Updated & Refined, Ready for Execution  
**Updated:** 2026-09-10  

---

## Phase Progress Summary

| Phase | Description | Status | Subagent Assigned |
|---|---|---|---|
| **Phase 01** | Core Architecture, Unified Identity & Appointment State Machine | Ready to Start | `cursor` (`composer-2.5`) |
| **Phase 02** | Doctor Onboarding & Verification Pipeline | Planned | `cursor` (`claude-opus-5-thinking-high`) |
| **Phase 03** | Patient Identity Specialization, Catalog & Real-Time Search Sync | Planned | `codex` (`gpt-5.6-terra`) |
| **Phase 04** | Scheduling, Atomic Slot Booking, Payments & Cancellation Engine | Planned | `cursor` (`composer-2.5`) |
| **Phase 05** | Node.js Real-Time Gateway & Redis Pub/Sub Bridge | Planned | `codex` (`gpt-5.6-terra`) |
| **Phase 06** | Teleconsultation Engine & Session Lifecycle | Planned | `cursor` (`claude-opus-5-thinking-high`) |
| **Phase 07** | Clinical Ops Queue & Structured Digital Prescriptions | Planned | `codex` (`gpt-5.6-terra`) |
| **Phase 08** | Admin Operations, Content Moderation & Audit Console | Planned | `cursor` (`claude-opus-5-thinking-high`) |
| **Phase 09** | End-to-End MVP Golden Loop Verification & Hardening | Planned | **09-01**: `cursor` (`claude-opus-5-thinking-high`)<br>**09-02**: `devin` (`SWE-1.6 Slow`) |

---

## Key Locked Architectural Decisions

1. **Unified Identity Moved to Phase 01**: Foundational User model, JWT signing/verification, and passwordless OTP mechanics reside in Phase 01, eliminating backwards auth dependencies for Doctor Onboarding (Phase 02) and Patient Portal (Phase 03).
2. **Cancellation & Refund Policy Engine Housed in Phase 04**: Automated, policy-driven cancellation eligibility (e.g. >= 2 hour cutoff) and automated Razorpay refunds are explicitly built into the Phase 04 booking & payment engine.
3. **Phase 09 Concurrency Split**: Concurrency stress testing (RUL-01..04) and race condition validation routed to `cursor` (`claude-opus-5-thinking-high`), while final docstrings, linting, and OpenAPI spec export are handled by `devin` (`SWE-1.6 Slow`).
4. **State Machine Precedence**: 8-state Appointment Lifecycle is the central relational and state anchor; Teleconsultation (5-state) and Verification (6-state) interlock with it.
5. **Architecture Split**: FastAPI modular monolith for core transactions; Node.js gateway for WebSockets and chat relay; Redis Pub/Sub as bridge.
6. **Hard Rule Enforcements**:
   - Zero double-booking enforced via Redis locks and PostgreSQL exclusion constraints.
   - Real-time search propagation on doctor visibility toggles.
   - Atomic slot reservation and Razorpay payment capture/rollback.
   - Immutable audit logging on every administrative mutation.
7. **Compliance Gates**:
   - Telemedicine restricted-drug-category flag requires legal sign-off before launch.
   - DPDP Act auditable consent component must precede public patient onboarding.
8. **Phase 2 Scope Boundary**: All 16 deferred items from PRD Section 3 are strictly fenced off from Phase 1.
