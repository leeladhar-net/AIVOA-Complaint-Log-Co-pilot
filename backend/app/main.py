from datetime import datetime
from io import BytesIO
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Base, engine, get_db
from .graph import chat_with_copilot, complaint_graph
from .models import Complaint
from .schemas import AnalyzeComplaintRequest, AnalysisResponse, ComplaintCreate, ComplaintResponse, CopilotChatRequest, CopilotChatResponse

Path("data").mkdir(exist_ok=True)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AIVOA Complaint QMS API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/complaints/analyze", response_model=AnalysisResponse)
def analyze_complaint(request: AnalyzeComplaintRequest):
    result = complaint_graph.invoke({"raw_text": request.complaint_text, "workflow_steps": []})
    return AnalysisResponse(draft=result["draft"], workflow_steps=result["workflow_steps"], provider=result["provider"])


@app.post("/api/copilot/chat", response_model=CopilotChatResponse)
def chat_with_complaint_copilot(request: CopilotChatRequest):
    return chat_with_copilot(request.message, request.draft)


@app.post("/api/documents/extract-text")
async def extract_document_text(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    content = await file.read()
    if suffix == ".txt":
        return {"text": content.decode("utf-8", errors="replace")}
    if suffix == ".pdf":
        reader = PdfReader(BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if not text:
            raise HTTPException(status_code=422, detail="No selectable text found in this PDF.")
        return {"text": text}
    raise HTTPException(status_code=415, detail="Please upload a .pdf or .txt complaint file.")


@app.post("/api/complaints", response_model=ComplaintResponse, status_code=201)
def create_complaint(payload: ComplaintCreate, db: Session = Depends(get_db)):
    next_id = (db.scalar(select(func.max(Complaint.id))) or 0) + 1
    record = Complaint(complaint_number=f"CC-{datetime.now():%Y}-{next_id:04d}", **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.get("/api/complaints", response_model=list[ComplaintResponse])
def list_complaints(db: Session = Depends(get_db)):
    return list(db.scalars(select(Complaint).order_by(Complaint.created_at.desc())))


# Serve frontend static assets from ../frontend/dist if it exists
frontend_dist_path = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist_path.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist_path / "assets"), name="assets")

    @app.get("/{fallback_path:path}")
    def serve_frontend(fallback_path: str):
        # Allow API routes to be handled properly (in case they fall through, but they shouldn't since they are matched first)
        if fallback_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        # Serve index.html for all other routes to support React SPA routing
        index_file = frontend_dist_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Index file not found")
