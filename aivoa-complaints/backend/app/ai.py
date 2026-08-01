import json
import logging
import os
import re
from pathlib import Path
from typing import TypedDict
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from .schemas import AnalysisResult, ComplaintDraft, RiskAssessment

# Loads local development secrets only; .env is ignored by git.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
logger = logging.getLogger(__name__)

class IntakeState(TypedDict, total=False):
    source_text: str
    complaint: dict
    summary: str
    risk_assessment: dict
    warnings: list[str]
    used_demo_mode: bool

SYSTEM_PROMPT = """You are an AI assistant for pharmaceutical quality complaint intake. Extract facts only from the complaint. Never invent values. Return one JSON object only, no markdown.

Required structure:
{
  "complaint": {"complaint_source": "Uploaded document / pasted text", "customer_name": null, "product_name": null, "product_strength": null, "batch_lot_number": null, "manufacturing_date": null, "expiry_date": null, "quantity_affected": null, "complaint_type": null, "complaint_date": null, "detailed_description": null, "initial_severity": "Minor|Major|Critical", "priority": "Low|Medium|High|Critical", "status": "Pending Triage"},
  "summary": "short factual summary",
  "warnings": ["missing or ambiguous information"]
}

Use null for unavailable values. Dates must be ISO format YYYY-MM-DD only; a month/year such as June 2028 is ambiguous, so use null and add a warning. status must always be Pending Triage. Do not assess risk; the separate Risk Analyzer performs that task. The final human QA reviewer makes all decisions."""

RISK_PROMPT = """You are an independent pharmaceutical QMS risk analyzer. Evaluate only the supplied structured complaint record. Return JSON only with this exact structure:
{"severity":"Minor|Major|Critical","priority":"Low|Medium|High|Critical","rationale":"brief evidence-based rationale","suggested_action":"brief QA next step","risk_mitigation":["immediate containment action"],"preventive_actions":["longer-term prevention action"]}
Do not invent missing facts. The result is a recommendation for a human QA reviewer, never a final quality or regulatory decision."""

def groq_completion(messages: list[dict], json_mode: bool = False) -> str:
    """Use Groq's native SDK; LangGraph orchestrates this function's caller."""
    from groq import Groq
    client = Groq(api_key=os.environ["GROQ_API_KEY"].strip(), timeout=25.0, max_retries=1)
    request = {
        "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip(),
        "messages": messages,
        "temperature": 0,
    }
    if json_mode:
        request["response_format"] = {"type": "json_object"}
    completion = client.chat.completions.create(**request)
    return completion.choices[0].message.content or ""

def demo_extract(text: str) -> dict:
    lower = text.lower()
    batch = re.search(r"(?:batch|lot)\s*(?:number|no\.?|#)?\s*[:#-]?\s*([A-Za-z0-9-]{3,})", text, re.I)
    quantity = re.search(r"(?:approximately|about|around)?\s*(\d+\s*(?:bottles|packs|units|tablets|strips))", lower)
    product = re.search(r"((?:paracetamol|amoxicillin|ibuprofen)[^,.\n]{0,35})", text, re.I)
    critical_words = ["adverse", "injury", "hospital", "safety", "contamination"]
    major_words = ["broken", "damage", "defect", "incorrect", "missing"]
    severity = "Critical" if any(w in lower for w in critical_words) else "Major" if any(w in lower for w in major_words) else "Minor"
    priority = "Critical" if severity == "Critical" else "High" if severity == "Major" else "Medium"
    complaint_type = "Potential safety concern" if severity == "Critical" else "Product defect" if severity == "Major" else "General quality concern"
    fields = {
        "complaint_source": "Uploaded document / pasted text", "customer_name": None,
        "product_name": product.group(1).strip() if product else None, "product_strength": None,
        "batch_lot_number": batch.group(1) if batch else None, "manufacturing_date": None,
        "expiry_date": None, "quantity_affected": quantity.group(1) if quantity else None,
        "complaint_type": complaint_type, "complaint_date": None,
        "detailed_description": text[:1500], "initial_severity": severity, "priority": priority,
        "status": "Pending Triage",
    }
    warnings = [f"{label} was not found; please verify or complete it." for key, label in [("customer_name", "Customer name"), ("product_name", "Product name"), ("batch_lot_number", "Batch/lot number")] if not fields[key]]
    return {"complaint": fields, "summary": f"Complaint draft created for {fields['product_name'] or 'an unspecified product'}{(' (batch ' + fields['batch_lot_number'] + ')') if fields['batch_lot_number'] else ''}.", "warnings": warnings, "used_demo_mode": True}

def normalize_ai_result(data: object) -> dict:
    """Make a model response safe for the typed UI contract; do not fabricate facts."""
    if not isinstance(data, dict):
        raise ValueError("Groq returned a non-object JSON response")
    supplied_complaint = data.get("complaint") if isinstance(data.get("complaint"), dict) else {}
    complaint = {key: supplied_complaint.get(key) for key in ComplaintDraft.model_fields}
    complaint["status"] = complaint.get("status") if isinstance(complaint.get("status"), str) else "Pending Triage"
    warnings = [str(item) for item in data.get("warnings", []) if isinstance(item, str)] if isinstance(data.get("warnings"), list) else []
    for key in ("manufacturing_date", "expiry_date", "complaint_date"):
        value = complaint.get(key)
        if value is not None and (not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)):
            complaint[key] = None
            warnings.append(f"{key.replace('_', ' ').title()} was ambiguous and needs QA verification.")
    if complaint.get("initial_severity") not in {"Minor", "Major", "Critical"}:
        complaint["initial_severity"] = None
    if complaint.get("priority") not in {"Low", "Medium", "High", "Critical"}:
        complaint["priority"] = None
    summary = data.get("summary") if isinstance(data.get("summary"), str) else "Complaint draft generated for QA review."
    return {"complaint": complaint, "summary": summary, "warnings": list(dict.fromkeys(warnings)), "used_demo_mode": False}

def extract_node(state: IntakeState):
    if not os.getenv("GROQ_API_KEY"):
        return demo_extract(state["source_text"])
    try:
        content = groq_completion([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": state["source_text"]},
        ], json_mode=True)
        return normalize_ai_result(json.loads(content))
    except Exception as exc:
        logger.exception("Groq complaint extraction failed: %s", exc)
        result = demo_extract(state["source_text"])
        result["warnings"].append(f"Live AI was unavailable ({type(exc).__name__}); a safe demo analysis was used. Check the backend terminal for the Groq error.")
        return result

def validate_node(state: IntakeState):
    # Validates model output against the API contract before it reaches the UI.
    validated = AnalysisResult.model_validate(state)
    return validated.model_dump(mode="json")

def build_graph():
    graph = StateGraph(IntakeState)
    graph.add_node("extract", extract_node)
    graph.add_node("validate", validate_node)
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "validate")
    graph.add_edge("validate", END)
    return graph.compile()

intake_graph = build_graph()

def analyze_text(text: str) -> AnalysisResult:
    result = intake_graph.invoke({"source_text": text})
    return AnalysisResult.model_validate(result)

def demo_risk(complaint: ComplaintDraft) -> RiskAssessment:
    text = " ".join(filter(None, [complaint.complaint_type, complaint.detailed_description])).lower()
    critical_words = ["adverse", "injury", "hospital", "safety", "contamination"]
    major_words = ["broken", "damage", "defect", "incorrect", "missing", "discolor"]
    severity = "Critical" if any(word in text for word in critical_words) else "Major" if any(word in text for word in major_words) else "Minor"
    priority = "Critical" if severity == "Critical" else "High" if severity == "Major" else "Medium"
    return RiskAssessment(
        severity=severity,
        priority=priority,
        rationale="Initial recommendation derived from the recorded complaint details. QA must verify the classification.",
        suggested_action="Review the affected batch, confirm product impact, and begin the appropriate QA triage.",
        risk_mitigation=["Place the implicated batch under QA review or quarantine as appropriate.", "Preserve the complaint evidence and confirm product traceability."],
        preventive_actions=["Investigate the probable root cause with manufacturing and packaging teams.", "Document corrective and preventive actions after QA review."],
    )

def assess_risk(complaint: ComplaintDraft) -> RiskAssessment:
    if not os.getenv("GROQ_API_KEY"):
        return demo_risk(complaint)
    try:
        content = groq_completion([
            {"role": "system", "content": RISK_PROMPT},
            {"role": "user", "content": complaint.model_dump_json()},
        ], json_mode=True)
        return RiskAssessment.model_validate(json.loads(content))
    except Exception as exc:
        logger.exception("Groq risk analysis failed: %s", exc)
        return demo_risk(complaint)

def copilot_reply(complaint: ComplaintDraft, question: str) -> dict:
    """Answer a question and apply only explicit, reviewable user-requested edits."""
    def fallback_reply() -> dict:
        updates = {}
        strength = re.search(r"(?:change|set|update).*?(?:strength|dose).*?(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml))", question, re.I)
        quantity = re.search(r"(?:change|set|update).*?(?:quantity|amount).*?(\d+\s*(?:capsules?|tablets?|bottles?|packs?|units?|strips?))", question, re.I)
        batch = re.search(r"(?:change|set|update).*?(?:batch|lot).*?([A-Z0-9-]{3,})", question, re.I)
        if strength: updates["product_strength"] = strength.group(1)
        if quantity: updates["quantity_affected"] = quantity.group(1)
        if batch: updates["batch_lot_number"] = batch.group(1)
        if updates:
            return {"answer": "I applied the specific update you requested. All other complaint details were preserved.", "field_updates": updates}
        missing = [name for name, value in [("customer name", complaint.customer_name), ("product name", complaint.product_name), ("batch/lot number", complaint.batch_lot_number), ("complaint description", complaint.detailed_description)] if not value]
        if "missing" in question.lower():
            return {"answer": "Please complete: " + (", ".join(missing) if missing else "the core intake fields are present") + ".", "field_updates": {}}
        return {"answer": "I can update a specific field when you state it clearly, for example: 'Change strength to 250 mg.' QA must review all changes before saving.", "field_updates": {}}

    if not os.getenv("GROQ_API_KEY"):
        return fallback_reply()

    allowed_fields = set(ComplaintDraft.model_fields)
    prompt = f"""You are AIVOA Copilot for pharmaceutical complaint intake.
Current complaint draft: {complaint.model_dump_json()}
User question or request: {question}

Return JSON only: {{"answer": "concise helpful answer", "field_updates": {{}}}}.
Answer questions clearly. Add field_updates only for fields the user explicitly changes, corrects, or supplies in this message. Return only the changed fields - never repeat unchanged values and never use an empty string to erase a field. Use only these field names: {sorted(allowed_fields)}. Do not invent facts or make final quality decisions; remind the user that QA must verify suggestions."""
    try:
        data = json.loads(groq_completion([{"role": "user", "content": prompt}], json_mode=True))
        answer = data.get("answer") if isinstance(data, dict) and isinstance(data.get("answer"), str) else "I could not produce a reliable answer. Please ask the QA team to review the complaint."
        updates = data.get("field_updates") if isinstance(data, dict) and isinstance(data.get("field_updates"), dict) else {}
        safe_updates = {key: str(value) for key, value in updates.items() if key in allowed_fields and isinstance(value, (str, int, float))}
        return {"answer": answer, "field_updates": safe_updates}
    except Exception as exc:
        logger.exception("Groq Copilot request failed: %s", exc)
        return fallback_reply()
