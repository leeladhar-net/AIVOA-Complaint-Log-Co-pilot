# AIVOA - AI Complaint Intake

An AI-assisted Customer Complaint Management module for pharmaceutical Quality Assurance teams. It converts a complaint document or email into a reviewable, structured complaint draft; the QA user verifies every value before saving.

## Architecture

```text
React + Redux workspace
        |
        v
FastAPI API -----> SQLite local database
        |
        v
LangGraph: extract -> validate -> assess -> return draft
        |
        v
Groq (Gemma 2), with a predictable demo fallback when no API key is set
```

## Run locally

Prerequisites: Node 20+ and Python 3.9+.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (usually `http://localhost:5173`). If that port is in use, Vite selects another local port automatically; the backend accepts it.

### Share with another developer

Share the repository/project folder, but never share `backend/.env` because it contains your API key. The recipient should create their own `backend/.env` from `backend/.env.example` only if they want live Groq AI. Without it, the complete app runs in safe demo mode with SQLite, so no PostgreSQL, Docker, or API key is required.

If their FastAPI server runs anywhere other than `http://localhost:8000`, copy `frontend/.env.example` to `frontend/.env` and set `VITE_API_URL` to the backend's API URL before starting Vite.

### Database

The project uses SQLite, stored locally at `backend/aivoa.db`. It needs no Docker, database server, or extra installation. When FastAPI starts, it creates the `complaints` and `duplicate_alerts` tables automatically.

## Demo input

Paste this into the assistant:

> Customer reports broken tablets in approximately 20 bottles of Paracetamol 500 mg Tablets from batch BT-204. The complaint was received today. Please investigate this product defect.

## Main endpoints

- `POST /api/intake/analyze` - pasted text or PDF/DOCX/TXT/EML upload
- `POST /api/complaints` - saves the reviewed complaint draft
- `POST /api/copilot/chat` - answers questions against the current draft
- `GET /api/health` - service health check

## Product decisions

- AI suggestions are drafts only; the UI explicitly requires QA review.
- Structured Pydantic validation protects the UI and database from malformed model output.
- LangGraph owns the AI sequence; FastAPI routes remain thin.
- Real OCR is intentionally out of scope, per the assignment brief.
