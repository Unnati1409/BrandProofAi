# Architecture Decision Records (ADRs)

**Project:** BrandProof AI  
**Team:** SAKHI  
**Repository:** Code Nexus Hackathon  

---

## ADR 001: Architecture & Technology Stack Selection
* **Date:** 2026-11-05
* **Status:** Accepted
* **Context:**
  BrandProof AI requires deterministic brand compliance verification combined with grounded AI claim evaluation. The system must operate without web search or ungrounded model knowledge, isolate multi-tenant data, and enforce strict human approval workflows.
* **Decision:**
  - Frontend: React 18 with TypeScript, Vite, and Tailwind CSS.
  - Backend: Python 3.10+ with FastAPI and Pydantic v2. This is the **only** component that interacts with Gemini and holds service keys.
  - Database: Supabase PostgreSQL 15+ with `pgvector` for exact nearest-neighbour cosine similarity and `tsvector` for full-text search.
  - Document Parsers: PyMuPDF for PDF text/offsets; python-docx for DOCX run formatting, shading, alt text, and headings.
  - Deployment: Vercel for frontend; Render for backend.
* **Consequences:**
  Eliminates separate vector DB infrastructure (no Pinecone/FAISS), centralizing data consistency, transactions, and RLS inside PostgreSQL.

---

## ADR 002: Seed Fictional Organization ("AuraHealth Technologies")
* **Date:** 2026-11-05
* **Status:** Accepted
* **Context:**
  The MVP requires realistic testing fixtures across all compliance categories (terminology, trademarks, required legal disclaimers, numeric claim validation, expired facts, and accessibility).
* **Decision:**
  Establish **"AuraHealth Technologies"** as the reference fictional entity.
  - Products: `AuraCare™ Enterprise`, `AuraPulse Analytics`, `AuraBridge EHR`.
  - Terminology Rules: Registered casing (`AuraCare`, not `Auracare` or `Aura Care`); banned terms (`guaranteed cure`, `100% bug-free`, `cheapest solution`).
  - Required Wording: Mandatory HIPAA and FDA compliance notices.
  - Facts: Official 2026 pricing ($499/month per clinic), 99.95% uptime SLA, and one expired fact (Q3 2025 Promotional Beta pricing expired Oct 1, 2025).
  - Palette: Slate `#0F172A`, Dark Teal `#0D9488`, Pure White `#FFFFFF`, and an intentionally failing low-contrast pair (`#94A3B8` on `#FFFFFF` = 2.9:1) for contrast testing.
* **Consequences:**
  Enables comprehensive automated golden tests without using real or confidential enterprise data.

---

## ADR 003: Design System Tokens & Anti-AI Visual Standards
* **Date:** 2026-11-05
* **Status:** Accepted
* **Context:**
  The platform must function as an institutional B2B editorial tool (comparable to Linear, Notion, or Stripe internal tooling). AI-generated visual clichés (purple gradients, glowing borders, glassmorphism, floating cards) degrade credibility.
* **Decision:**
  - Single neutral typography family (Inter/system sans) plus monospace (`JetBrains Mono` / `ui-monospace`) for codes and quotations.
  - Deliberate type scale: 12px, 13px, 14px (dense default body), 16px, 20px, 24px, 30px with tabular numerals (`tnum`).
  - Palette tokens: Neutral zinc/slate greys, exactly ONE primary action/focus accent (`slate-900`/`indigo-600`), and separate semantic tokens for status and severity.
  - Information Density: Tables, split panes, and compact lists over cards.
  - Dual-channel accessibility: Severity and verdicts never rely on color alone; always paired with shape/icon and text labels meeting WCAG 2.1 AA.
* **Consequences:**
  Creates a serious, high-productivity compliance tool tailored for brand managers and legal reviewers.

---

## ADR 004: Python & Node Runtime Setup on Windows
* **Date:** 2026-11-05
* **Status:** Accepted
* **Context:**
  The host environment is Windows with Node 25.6.1 and Python 3.10.0 installed at `C:\Users\Shristi\AppData\Local\Programs\Python\Python310\python.exe`. The default `python.exe` execution alias points to the WindowsApps stub which was disabled.
* **Decision:**
  Standardize backend execution through a dedicated virtual environment (`backend/venv`) created using Python 3.10. All scripts and commands will invoke `backend/venv/Scripts/python.exe` and `backend/venv/Scripts/pytest.exe`.
* **Consequences:**
  Ensures isolation, reproducible package resolution, and seamless multi-platform execution.

---

## ADR 005: Strict Database Isolation & Creator Separation of Concerns
* **Date:** 2026-11-05
* **Status:** Accepted
* **Context:**
  Security and editorial ethics dictate that creators must never approve their own content, and multi-tenant data must never leak across workspace boundaries.
* **Decision:**
  Enforce creator separation at both the API layer (HTTP 403) and at the PostgreSQL database engine level using a CHECK constraint / trigger on `content_approvals`. All queries must be scoped by `workspace_id`.
* **Consequences:**
  Prevents self-approval exploits even if the API layer is bypassed via direct SQL or misconfigured client calls.

---

## ADR 006: Direct Bcrypt Password Hashing & PyJWT Token Authentication
* **Date:** 2026-11-07
* **Status:** Accepted
* **Context:**
  Legacy `passlib` has compatibility issues with modern bcrypt (version 4.1+/5.0+) and PyJWT token decode without explicit audience specification can permit token replay across environments.
* **Decision:**
  - Implement direct `bcrypt` password hashing with explicit 72-byte truncation safety (`pwd_bytes = password.encode('utf-8')[:72]`) and salt generation.
  - Implement PyJWT encoding and decoding with enforced claims: `sub`, `email`, `aud="authenticated"`, `exp`, and standard HMAC-SHA256 signing.
* **Consequences:**
  Eliminates passlib deprecation warnings, prevents bcrypt truncation vulnerabilities, and ensures robust token verification.

---

## ADR 007: External AI Disclosure Gate & Deterministic Fallback Principle
* **Date:** 2026-11-07
* **Status:** Accepted
* **Context:**
  Enterprise brand governance platforms handle proprietary marketing materials. Users must know precisely when and what data is shared with external AI services, and must have the option to operate in a 100% private deterministic mode.
* **Decision:**
  - Require explicit Administrator acknowledgment of the Google Gemini External AI Disclosure before `ai_enabled` can be activated for any workspace.
  - When AI is disabled, the platform executes deterministic checks only (exact terminology, casing, banned terms, required wording, expired facts, and WCAG contrast).
  - Gemini suggestions are strictly advisory (`AI-assisted (Advisory)`), grounded exclusively in confirmed workspace guidelines, and AI possesses zero approval permission in the data model.
* **Consequences:**
  Satisfies strict enterprise compliance, prevents silent data transmission, and ensures uninterrupted operation even without external AI keys.
