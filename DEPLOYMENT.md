# AIVOA Complaint QMS — Deployment Guide

This document describes how to build, run, and submit the **AIVOA Complaint QMS** project.

---

## 📋 Prerequisites

To run this application locally, you will need:
1. **Python 3.10+** (with the `py` launcher on Windows or `python3` on Unix/macOS)
2. **Node.js 18+** & **npm** (for building/compiling the frontend static assets)

---

## 🚀 Option A: Single-Server Deployment (Recommended for Submission)

This is the easiest way to run the project. You build the React frontend into static HTML/JS/CSS assets, and the FastAPI backend serves both the API endpoints and the frontend client on the exact same port (`8000`).

### Step-by-Step:

1. **Build the Frontend Assets:**
   Open a terminal in the `frontend` directory and run:
   ```powershell
   cd frontend
   npm install
   npm run build
   ```
   *This compiles the React app into static files in `frontend/dist`.*

2. **Set Up the Backend Environment:**
   Open a terminal in the `backend` directory and run:
   ```powershell
   cd backend
   py -m venv .venv
   .\.venv\Scripts\python -m pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

3. **Configure the AI (Optional):**
   Open `backend/.env` and insert your API key to run with live AI analysis:
   ```env
   GROQ_API_KEY=your-actual-groq-api-key-here
   ```
   *If `GROQ_API_KEY` is left blank, the application automatically runs in a deterministic local fallback/safe demo mode. No internet or API key required.*

4. **Launch the Server:**
   From the `backend` directory, run:
   ```powershell
   .\.venv\Scripts\python -m uvicorn app.main:app --port 8000
   ```

5. **Access the App:**
   Open your browser and navigate to:
   👉 **[http://localhost:8000](http://localhost:8000)**

---

## 🛠️ Option B: Two-Terminal Development Mode

If you need to edit React files or backend code with hot-reloading (live update upon save), run the frontend and backend in separate terminal sessions.

### Terminals Needed:

### 1. Terminal 1: Backend API
Navigate to the `backend` directory, activate the virtual environment, and run:
```powershell
cd backend
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```
*The API endpoints will be running on `http://127.0.0.1:8000/api`.*

### 2. Terminal 2: Vite Development Server
Navigate to the `frontend` directory and run:
```powershell
cd frontend
npm run dev
```
*The Vite development server will launch the UI on `http://localhost:5173` (or the next available port).*

---

## 📁 Project Structure Summary

* [**`backend/app/main.py`**](file:///backend/app/main.py): FastAPI API routes, CORS rules, and static file mounting.
* [**`backend/app/graph.py`**](file:///backend/app/graph.py): LangGraph workflow (Extract $\rightarrow$ Validate $\rightarrow$ Assess $\rightarrow$ Risk Recommendation).
* [**`frontend/src/App.tsx`**](file:///frontend/src/App.tsx): Core React UI component for parsing documents and chatting with the copilot.
* [**`backend/data/aivoa_qms.db`**](file:///backend/data/): Automatically created SQLite database where committed complaints are persisted.
