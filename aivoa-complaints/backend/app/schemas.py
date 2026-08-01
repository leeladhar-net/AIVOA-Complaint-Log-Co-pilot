from __future__ import annotations
from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

Severity = Literal["Minor", "Major", "Critical"]
Priority = Literal["Low", "Medium", "High", "Critical"]

class ComplaintDraft(BaseModel):
    complaint_source: Optional[str] = None
    customer_name: Optional[str] = None
    product_name: Optional[str] = None
    product_strength: Optional[str] = None
    batch_lot_number: Optional[str] = None
    manufacturing_date: Optional[date] = None
    expiry_date: Optional[date] = None
    quantity_affected: Optional[str] = None
    complaint_type: Optional[str] = None
    complaint_date: Optional[date] = None
    detailed_description: Optional[str] = None
    initial_severity: Optional[Severity] = None
    priority: Optional[Priority] = None
    status: str = "Pending Triage"

    @field_validator("manufacturing_date", "expiry_date", "complaint_date", mode="before")
    @classmethod
    def empty_date_is_missing(cls, value):
        # HTML date inputs send an empty string when no date is selected.
        return None if value == "" else value

class RiskAssessment(BaseModel):
    severity: Severity
    priority: Priority
    rationale: str
    suggested_action: str
    risk_mitigation: list[str] = Field(default_factory=list)
    preventive_actions: list[str] = Field(default_factory=list)

class AnalysisResult(BaseModel):
    complaint: ComplaintDraft
    summary: str
    warnings: list[str] = Field(default_factory=list)
    used_demo_mode: bool = False

class RiskAnalysisRequest(BaseModel):
    complaint: ComplaintDraft

class SaveComplaintRequest(ComplaintDraft):
    ai_summary: Optional[str] = None
    risk_rationale: Optional[str] = None
    source_text: Optional[str] = None

class SavedComplaint(BaseModel):
    id: int
    complaint_number: str
    status: str
    created_at: datetime
    duplicate_matches: list["DuplicateMatch"] = Field(default_factory=list)

class DuplicateMatch(BaseModel):
    complaint_number: str
    customer_name: Optional[str] = None
    product_name: Optional[str] = None
    batch_lot_number: Optional[str] = None
    complaint_type: Optional[str] = None
    reason: str
    notification_note: str

class DuplicateCheckResponse(BaseModel):
    matches: list[DuplicateMatch] = Field(default_factory=list)

class CopilotRequest(BaseModel):
    complaint: ComplaintDraft
    question: str = Field(min_length=2, max_length=1500)

class CopilotResponse(BaseModel):
    answer: str
    field_updates: dict[str, str] = Field(default_factory=dict)
