import re
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .config import get_settings
from .schemas import ComplaintDraft, CopilotChatResponse


class ComplaintState(TypedDict, total=False):
    raw_text: str
    draft: ComplaintDraft
    workflow_steps: list[str]
    provider: str


SYSTEM_PROMPT = """You are an AI copilot for a pharmaceutical Quality Management System.
Extract a customer complaint into the provided schema. Do not invent identifiers, dates, or
customer names. For missing values use an empty string. Classify severity as Minor, Major, or
Critical. Treat possible product-quality defects involving a distributed medicine as at least
Major unless the text clearly supports a lower severity. Make recommendations concise and
appropriate for QA triage. This is a draft for human review, not a final quality decision."""


def _fallback_extract(text: str) -> ComplaintDraft:
    """Deterministic local mode so the product remains demoable without a Groq key."""
    lowered = text.lower()
    batch = re.search(r"(?:batch(?:\s+(?:number|no\.?))?|lot(?:\s+(?:number|no\.?))?)\s*[:#-]?\s*([A-Z0-9-]{4,})", text, re.I)
    strength = re.search(r"\b(\d+(?:\.\d+)?\s?(?:mg|mcg|g|ml|%))\b", text, re.I)
    quantity = re.search(r"\b(\d+\s+(?:capsules?|tablets?|bottles?|units?|vials?))\b", text, re.I)
    manufactured = re.search(r"manufactur(?:ing|ed)\s+(?:date)?\s*[:#-]?\s*([A-Za-z]+\s+\d{4})", text, re.I)
    expiry = re.search(r"expir(?:y|y date|es)\s*(?:date)?\s*[:#-]?\s*([A-Za-z]+\s+\d{4})", text, re.I)
    customer_match = re.search(r"^\s*([A-Z][A-Za-z0-9& .'-]+?)\s+(?:reported|complained|notified)", text)
    product_match = re.search(r"(?:in|for)\s+([A-Z][A-Za-z0-9 -]+?)\s+(\d+(?:\.\d+)?\s?(?:mg|mcg|g|ml|%))", text)

    if "discolor" in lowered or "discolour" in lowered:
        category = "Product Defect - Discoloration"
        risk = "Potential degradation, moisture ingress, or primary-packaging seal failure may have caused discoloration. Quarantine the implicated batch pending QA investigation."
    elif "broken" in lowered or "crack" in lowered:
        category = "Packaging Defect"
        risk = "Possible packaging-integrity failure. Assess whether the product was exposed to contamination or environmental conditions."
    else:
        category = "Product Quality Complaint"
        risk = "Assess the reported issue, impacted batch, and potential patient impact through the QA investigation process."

    return ComplaintDraft(
        complaint_source="Pharmacy" if "pharmacy" in lowered else "Customer",
        customer_name=customer_match.group(1).strip() if customer_match else "",
        product_name=product_match.group(1).strip() if product_match else "",
        product_strength=strength.group(1) if strength else "",
        batch_number=batch.group(1) if batch else "",
        affected_quantity=quantity.group(1) if quantity else "",
        manufacturing_date=manufactured.group(1) if manufactured else "",
        expiry_date=expiry.group(1) if expiry else "",
        originating_site_block="Pending QA confirmation",
        impacted_materials="Primary packaging (to be investigated)",
        complaint_category=category,
        complaint_description=text.strip(),
        severity="Major" if any(word in lowered for word in ("discolor", "discolour", "broken", "crack")) else "Minor",
        suggested_next_action="Route to QA Investigation and assess product replacement",
        initial_risk_assessment=risk,
    )


def extract_complaint(state: ComplaintState) -> ComplaintState:
    settings = get_settings()
    text = state["raw_text"]
    steps = state.get("workflow_steps", []) + ["Extracted complaint fields"]

    if not settings.groq_api_key:
        return {"draft": _fallback_extract(text), "workflow_steps": steps, "provider": "local fallback"}

    # The Groq call is isolated here so all later nodes receive the same validated schema.
    from langchain_groq import ChatGroq

    model = ChatGroq(model=settings.groq_model, temperature=0, api_key=settings.groq_api_key)
    extractor = model.with_structured_output(ComplaintDraft)
    draft = extractor.invoke([("system", SYSTEM_PROMPT), ("human", text)])
    return {"draft": draft, "workflow_steps": steps, "provider": f"Groq {settings.groq_model}"}


def validate_completeness(state: ComplaintState) -> ComplaintState:
    draft = state["draft"]
    missing = [label for label, value in {
        "customer name": draft.customer_name,
        "product name": draft.product_name,
        "batch number": draft.batch_number,
        "complaint description": draft.complaint_description,
    }.items() if not value]
    steps = state["workflow_steps"] + ["Validated required complaint fields"]
    if missing:
        draft.initial_risk_assessment = f"Missing information: {', '.join(missing)}. {draft.initial_risk_assessment}".strip()
    return {"draft": draft, "workflow_steps": steps}


def finalize_risk(state: ComplaintState) -> ComplaintState:
    draft = state["draft"]
    steps = state["workflow_steps"] + ["Generated initial QA risk recommendation"]
    if not draft.severity:
        draft.severity = "Minor"
    return {"draft": draft, "workflow_steps": steps}


def build_complaint_graph():
    graph = StateGraph(ComplaintState)
    graph.add_node("extract_complaint", extract_complaint)
    graph.add_node("validate_completeness", validate_completeness)
    graph.add_node("finalize_risk", finalize_risk)
    graph.add_edge(START, "extract_complaint")
    graph.add_edge("extract_complaint", "validate_completeness")
    graph.add_edge("validate_completeness", "finalize_risk")
    graph.add_edge("finalize_risk", END)
    return graph.compile()


complaint_graph = build_complaint_graph()


def chat_with_copilot(message: str, draft: ComplaintDraft) -> CopilotChatResponse:
    """Answer a QMS question and optionally return safe, explicit field updates."""
    settings = get_settings()
    editable_fields = ", ".join(ComplaintDraft.model_fields.keys())
    if not settings.groq_api_key:
        lowered = message.lower()
        if "severity" in lowered:
            return CopilotChatResponse(message=f"The current suggested severity is {draft.severity or 'not yet assessed'}. A human QA reviewer should confirm it before committing.")
        if "batch" in lowered:
            return CopilotChatResponse(message=f"The recorded batch number is {draft.batch_number or 'missing'}.")
        return CopilotChatResponse(message="I can answer questions about the current complaint and suggest edits. Add a Groq API key for richer conversational responses.")

    from langchain_groq import ChatGroq

    prompt = f"""You are AIVOA Copilot, a helpful pharmaceutical QMS assistant. Answer the user's question briefly and clearly. You may suggest edits to the complaint form only when the user explicitly asks to change a value. Return only fields that should change, using these exact snake_case names: {editable_fields}. Do not make up information; if information is unknown, explain that it needs QA confirmation. This is an assistive draft, not a final quality decision.

Current complaint draft:
{draft.model_dump_json(indent=2)}

User message: {message}"""
    model = ChatGroq(model=settings.groq_model, temperature=0, api_key=settings.groq_api_key)
    responder = model.with_structured_output(CopilotChatResponse)
    return responder.invoke(prompt)
