from __future__ import annotations
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .ai import analyze_text, assess_risk, copilot_reply
from .database import Complaint, DuplicateAlert, SessionLocal, init_db
from .schemas import AnalysisResult, ComplaintDraft, CopilotRequest, CopilotResponse, DuplicateCheckResponse, DuplicateMatch, RiskAnalysisRequest, RiskAssessment, SaveComplaintRequest, SavedComplaint

app = FastAPI(title="AIVOA Complaint Intake API", version="0.1.0")
# Vite picks the next available local port (for example 5174) if 5173 is busy.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup(): init_db()

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def extract_document_text(file: UploadFile, content: bytes) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix in {".txt", ".eml"}:
        return content.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
    if suffix == ".docx":
        from docx import Document
        return "\n".join(p.text for p in Document(BytesIO(content)).paragraphs)
    raise HTTPException(400, "Supported formats are PDF, DOCX, TXT, and EML.")

@app.get("/api/health")
def health(): return {"status": "ok"}

@app.post("/api/intake/analyze", response_model=AnalysisResult)
async def analyze(text: Optional[str] = Form(default=None), file: Optional[UploadFile] = File(default=None)):
    if file:
        content = await file.read()
        if len(content) > 10 * 1024 * 1024: raise HTTPException(400, "Maximum upload size is 10 MB.")
        text = extract_document_text(file, content)
    if not text or len(text.strip()) < 10: raise HTTPException(400, "Provide a complaint message or supported document with readable text.")
    return analyze_text(text.strip())

@app.post("/api/risk/analyze", response_model=RiskAssessment)
def analyze_risk(request: RiskAnalysisRequest):
    return assess_risk(request.complaint)

def clean(value: Optional[str]) -> str:
    return (value or "").strip().casefold()

def duplicate_matches(draft: ComplaintDraft, db: Session, exclude_id: Optional[int] = None) -> list[DuplicateMatch]:
    """Return high-confidence matches: same customer and product plus one supporting detail."""
    matches = []
    for record in db.query(Complaint).order_by(Complaint.created_at.desc()).all():
        if exclude_id and record.id == exclude_id: continue
        if not clean(draft.customer_name) or not clean(draft.product_name): continue
        if clean(record.customer_name) != clean(draft.customer_name) or clean(record.product_name) != clean(draft.product_name): continue
        evidence = []
        if clean(draft.batch_lot_number) and clean(record.batch_lot_number) == clean(draft.batch_lot_number): evidence.append("same batch/lot")
        if clean(draft.complaint_type) and clean(record.complaint_type) == clean(draft.complaint_type): evidence.append("same complaint type")
        if not evidence: continue
        reason = f"Same customer and product; {', '.join(evidence)}."
        matches.append(DuplicateMatch(complaint_number=record.complaint_number, customer_name=record.customer_name, product_name=record.product_name, batch_lot_number=record.batch_lot_number, complaint_type=record.complaint_type, reason=reason, notification_note="QA team should review this possible duplicate and notify the complaint owner/customer contact according to the company SOP."))
    return matches

@app.post("/api/duplicates/check", response_model=DuplicateCheckResponse)
def check_duplicates(draft: ComplaintDraft, db: Session = Depends(get_db)):
    return DuplicateCheckResponse(matches=duplicate_matches(draft, db))

@app.post("/api/complaints", response_model=SavedComplaint, status_code=201)
def save_complaint(payload: SaveComplaintRequest, db: Session = Depends(get_db)):
    number = f"CC-{datetime.now():%Y}-{datetime.now():%H%M%S}"
    record = Complaint(complaint_number=number, **payload.model_dump())
    db.add(record); db.commit(); db.refresh(record)
    matches = duplicate_matches(payload, db, exclude_id=record.id)
    for match in matches:
        other = db.query(Complaint).filter(Complaint.complaint_number == match.complaint_number).first()
        if other:
            db.add(DuplicateAlert(complaint_id=record.id, matching_complaint_id=other.id, reason=match.reason, notification_note=match.notification_note))
    if matches: db.commit()
    return SavedComplaint(id=record.id, complaint_number=record.complaint_number, status=record.status, created_at=record.created_at, duplicate_matches=matches)

@app.post("/api/copilot/chat", response_model=CopilotResponse)
def copilot(request: CopilotRequest):
    return CopilotResponse(**copilot_reply(request.complaint, request.question))
