# BrandProof AI

> **"An Intelligent Guardian for Every Brand"**  
> An enterprise pre-publication brand-governance and editorial compliance platform.  
> Code Nexus Hackathon — Team SAKHI

---

## 1. Overview & Core Principles

BrandProof AI prevents brand drift, ungrounded claims, and editorial non-compliance before content is published. Guidelines (PDF/DOCX) are ingested and confirmed by Brand Owners into an immutable, versioned catalogue. Content submitted by Creators undergoes an automated deterministic and advisory AI validation pipeline. Findings provide verifiable citations and diff suggestions before human Reviewers and Managers grant publication clearance.

### Guiding Principles
1. **Approved Sources Only:** Verification evaluates content strictly against confirmed organizational sources, never open web searches or general LLM knowledge.
2. **Deterministic Rules Over AI:** Terminology, prohibited phrases, required wording, product naming/casing, and expired facts are verified via exact algorithms. AI is strictly advisory (`AI-assisted (Advisory)`).
3. **People Decide (Zero Autonomous AI Approvals):** The AI cannot approve content. Separation of concerns is enforced: a creator cannot approve their own submissions (enforced at both API and database levels).

---

## 2. Technology Stack & Actual Implementation

- **Frontend:** React 18, TypeScript, Tailwind CSS, Vite, Lucide Icons.
- **Backend:** Python 3.10+, FastAPI, Pydantic v2, Uvicorn, SQLAlchemy 2.0, psycopg 3, HTTPX.
- **Document Ingestion:** `pypdf` for PDF character & passage extraction; Python Standard Library (`xml.etree` & `zipfile`) for Microsoft Word (.docx) XML inspection.
- **Database & Auth:** Supabase PostgreSQL 15+ (with Row-Level Security, multi-tenant isolation, immutability triggers) and Supabase Auth (JWT verification). Compatible with SQLite for standalone local unit testing.
- **AI Engine:** Google Gemini API (via HTTPX REST calls for structured JSON claim verification grounded in confirmed facts).
- **Deployment:** Vercel (Frontend), Render (Backend).

### Feature Implementation Status (Honest Capability Disclosure)

| Feature | Implemented? | Details |
| :--- | :--- | :--- |
| **PDF & DOCX Guideline Ingestion** | Yes | Parsed into structured clauses with page & paragraph references |
| **Candidate Rule/Fact Confirmation** | Yes | Extracted guidelines remain candidates until confirmed by Brand Owner |
| **Deterministic Banned Terms Check** | Yes | Exact offset matching, replacement suggestions |
| **Deterministic Required Wording** | Yes | Enforces required legal/brand statements |
| **Product Casing & Terminology** | Yes | Enforces exact canonical naming and casing |
| **Expired Approved Facts Filtering** | Yes | Expired facts excluded from active verification |
| **Advisory Gemini Claim Verification**| Yes | Structured JSON verification against confirmed facts |
| **Creator Self-Approval Prevention** | Yes | Enforced at both FastAPI dependency layer and database trigger level |
| **Tamper-Evident Audit Certificate** | Yes | SHA-256 audit hash exported with approved content |
| **pgvector Cosine Retrieval** | Partially Implemented | Database columns and schema prepared; review engine queries confirmed facts directly |
| **PostgreSQL Full-Text Search (tsvector)** | Not Implemented | Reserved for future scale; exact substring and fact retrieval used currently |
| **WCAG Color Contrast Checking** | Not Implemented | Structural and heading accessibility verified; pixel-level color contrast analyzer unfinished |

---

## 3. Repository Structure

```
├── .github/workflows/ci.yml       # Automated GitHub Actions CI pipeline
├── backend/                       # Python FastAPI backend service
│   ├── app/
│   │   ├── api/v1/                # REST API routes and versioned endpoints
│   │   ├── core/                  # Config, security, logging, rate limiting, errors
│   │   ├── db/                    # SQLAlchemy engine and EnforcedUnitOfWorkSession
│   │   ├── models/                # SQLAlchemy models (guidelines, rules, content, audit)
│   │   ├── schemas/               # Pydantic v2 validation contracts
│   │   └── services/              # Ingestion, extraction, review engine
│   ├── tests/                     # Unit, API, security, and workflow test suites
│   ├── requirements.txt           # Python dependencies
│   └── pyproject.toml             # Ruff and pytest configurations
├── frontend/                      # React TypeScript Vite frontend
│   ├── src/
│   │   ├── components/ui/         # 22 reusable enterprise UI primitives
│   │   ├── components/layout/     # AppShell, Sidebar, TopBar
│   │   ├── context/               # AuthContext and WorkspaceContext
│   │   ├── lib/                   # apiFetch client and Supabase client
│   │   ├── pages/                 # Guidelines, Content, Rules, Members, Dashboard
│   │   └── types/                 # Strict TypeScript contracts
│   ├── package.json
│   └── vercel.json                # Vercel SPA routing configuration
├── scripts/                       # Database seed and demo provisioning scripts
├── supabase/migrations/           # Production PostgreSQL migrations & RLS policies
├── render.yaml                    # Render backend deployment blueprint
├── docs/                          # Architecture decisions and progress tracking
└── README.md
```

---

## 4. Setup & Local Development

### Prerequisites
- Node.js 20+ and npm
- Python 3.10+ (with venv)
- Git
- (Optional) Supabase account or Supabase CLI for PostgreSQL RLS testing

### 1. Environment Setup

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Configure your Supabase URL, Anon Key, and Gemini API Key in `.env`.

### 2. Backend Setup & Run

```bash
cd backend
python -m venv venv

# Windows:
.\venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

pip install -r requirements.txt

# Run backend development server:
uvicorn app.main:app --reload --port 8000
```
Backend API: `http://localhost:8000`  
Interactive OpenAPI documentation: `http://localhost:8000/docs`  
Health endpoint: `http://localhost:8000/api/v1/health`

### 3. Frontend Setup & Run

```bash
cd frontend
npm install

# Start development server:
npm run dev
```
Frontend application: `http://localhost:5173`

### 4. Demo Account Setup (Optional)

To use the demo quick-fill buttons on the login screen (`admin@aurahealth.demo` / `creator@aurahealth.demo`):
```bash
python scripts/seed_demo_accounts.py
```
Alternatively, use the **Register** link on the login screen to register your own account.

---

## 5. Running Test Suites

### Backend Tests (Pytest & Ruff)
```bash
cd backend
.\venv\Scripts\activate

# Linting:
ruff check .

# Run Unit & Core Workflow Tests (SQLite-compatible, no external DB needed):
pytest -v -m "not postgres"

# Run All Tests (including PostgreSQL RLS integration tests, requires local Supabase on port 54322):
pytest -v
```

### Frontend Tests (Vitest & Type-Check & Build)
```bash
cd frontend

# TypeScript type checking:
npm run type-check

# Unit tests:
npm test -- --run

# Production build:
npm run build
```

---

## 6. Deployment Instructions

### Frontend (Vercel)
1. Import the repository in Vercel.
2. Set Root Directory to `frontend`.
3. Configure Environment Variables:
   - `VITE_API_BASE_URL`: Deployed backend URL (e.g., `https://brandproof-backend.onrender.com`)
   - `VITE_SUPABASE_URL`: Your Supabase Project URL
   - `VITE_SUPABASE_ANON_KEY`: Your Supabase Project Anon Key
4. Deploy! `frontend/vercel.json` ensures SPA client-side routing rewrites work out-of-the-box.

### Backend (Render)
1. In Render, select **New Web Service** and connect this repository (or use the blueprint with `render.yaml`).
2. Set Root Directory to `backend`.
3. Set Build Command: `pip install --upgrade pip && pip install -r requirements.txt`
4. Set Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Configure Environment Variables:
   - `ENVIRONMENT`: `production`
   - `FRONTEND_URL`: Your Vercel frontend URL (for CORS)
   - `DATABASE_URL`: Your Supabase PostgreSQL connection string (Transaction pooler)
   - `SUPABASE_URL`: Your Supabase Project URL
   - `SUPABASE_ANON_KEY`: Your Supabase Anon Key
   - `SUPABASE_JWT_SECRET`: Your Supabase JWT Secret (from Supabase Project Settings > API)
   - `SUPABASE_SERVICE_ROLE_KEY`: Your Supabase Service Role Key
   - `GEMINI_API_KEY`: Your Google Gemini API Key
   - `GEMINI_TEXT_MODEL`: `gemini-1.5-flash`
6. Deploy! Render will monitor `/api/v1/health` for zero-downtime health checks.

---

## 7. Known Limitations
- **WCAG Luminance Contrast:** Structure, headings, and alt text are audited; automated pixel color extraction from raster imagery is scheduled for Round 3.
- **pgvector Cosine Search:** Database vector columns exist in migrations; current retrieval uses workspace-filtered confirmed facts.
- **PostgreSQL Full-Text Search:** Full tsvector inverted index retrieval is not yet active.
