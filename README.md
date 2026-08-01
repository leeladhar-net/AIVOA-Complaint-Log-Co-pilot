# AIVOA Complaint QMS

An AI-assisted customer-complaint intake application for pharmaceutical manufacturing. Users can paste a complaint or upload a document, review AI-extracted data, assess risk, and save the reviewed complaint to a QMS ledger.

## Technology

- Frontend: React, TypeScript, Redux Toolkit
- Backend: FastAPI, SQLAlchemy
- AI orchestration: LangGraph
- Database: SQLite for local development; PostgreSQL-ready configuration

## Planned workflow

1. A user pastes a complaint or uploads a file.
2. The backend extracts the text and sends it through a LangGraph workflow.
3. The workflow produces a validated complaint draft and risk recommendation.
4. The user reviews and edits the draft.
5. The application commits the final record to the QMS ledger.

## Run locally

Open two terminals from the project root.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Add GROQ_API_KEY=your_key to .env for live Groq analysis.
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Without a Groq key, the exact same LangGraph workflow uses a deterministic local extractor. This is useful for development and a reliable fallback in the demo.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The frontend calls `http://127.0.0.1:8000/api` by default. To change it, set `VITE_API_URL` in `frontend/.env`.

## Key API routes

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/api/complaints/analyze` | Runs the LangGraph extraction, validation, and risk workflow. |
| `POST` | `/api/documents/extract-text` | Extracts selectable text from a PDF or text file. |
| `POST` | `/api/complaints` | Saves the reviewed complaint to the QMS ledger. |
| `GET` | `/api/complaints` | Lists committed complaints. |
