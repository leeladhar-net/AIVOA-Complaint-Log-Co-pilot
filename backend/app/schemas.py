from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ComplaintDraft(BaseModel):
    complaint_source: str = ""
    customer_name: str = ""
    product_name: str = ""
    product_strength: str = ""
    batch_number: str = ""
    affected_quantity: str = ""
    manufacturing_date: str = ""
    expiry_date: str = ""
    originating_site_block: str = ""
    impacted_materials: str = ""
    complaint_category: str = ""
    complaint_description: str = ""
    severity: str = ""
    suggested_next_action: str = ""
    initial_risk_assessment: str = ""


class AnalyzeComplaintRequest(BaseModel):
    complaint_text: str = Field(min_length=5, max_length=30000)


class AnalysisResponse(BaseModel):
    draft: ComplaintDraft
    workflow_steps: list[str]
    provider: str


class ComplaintCreate(ComplaintDraft):
    pass


class ComplaintResponse(ComplaintDraft):
    model_config = ConfigDict(from_attributes=True)

    id: int
    complaint_number: str
    status: str
    created_at: datetime


class CopilotChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=8000)
    draft: ComplaintDraft


class CopilotChatResponse(BaseModel):
    message: str
    field_updates: dict[str, str] = Field(default_factory=dict)
