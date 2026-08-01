import type { ComplaintDraft } from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api";

type ApiDraft = {
  complaint_source: string; customer_name: string; product_name: string; product_strength: string;
  batch_number: string; affected_quantity: string; manufacturing_date: string; expiry_date: string;
  originating_site_block: string; impacted_materials: string; complaint_category: string;
  complaint_description: string; severity: string; suggested_next_action: string;
  initial_risk_assessment: string;
};

const toDraft = (api: ApiDraft): ComplaintDraft => ({
  complaintSource: api.complaint_source, customerName: api.customer_name, productName: api.product_name,
  productStrength: api.product_strength, batchNumber: api.batch_number, affectedQuantity: api.affected_quantity,
  manufacturingDate: api.manufacturing_date, expiryDate: api.expiry_date, originatingSiteBlock: api.originating_site_block,
  impactedMaterials: api.impacted_materials, complaintCategory: api.complaint_category,
  complaintDescription: api.complaint_description, severity: api.severity,
  suggestedNextAction: api.suggested_next_action, initialRiskAssessment: api.initial_risk_assessment
});

const toApiDraft = (draft: ComplaintDraft): ApiDraft => ({
  complaint_source: draft.complaintSource, customer_name: draft.customerName, product_name: draft.productName,
  product_strength: draft.productStrength, batch_number: draft.batchNumber, affected_quantity: draft.affectedQuantity,
  manufacturing_date: draft.manufacturingDate, expiry_date: draft.expiryDate, originating_site_block: draft.originatingSiteBlock,
  impacted_materials: draft.impactedMaterials, complaint_category: draft.complaintCategory,
  complaint_description: draft.complaintDescription, severity: draft.severity,
  suggested_next_action: draft.suggestedNextAction, initial_risk_assessment: draft.initialRiskAssessment
});

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Unexpected server error" }));
    throw new Error(body.detail ?? "Request failed");
  }
  return response.json() as Promise<T>;
}

export async function analyzeComplaint(complaintText: string) {
  const response = await request<{ draft: ApiDraft; workflow_steps: string[]; provider: string }>("/complaints/analyze", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ complaint_text: complaintText })
  });
  return { draft: toDraft(response.draft), steps: response.workflow_steps, provider: response.provider };
}

export async function saveComplaint(draft: ComplaintDraft) {
  return request<{ complaint_number: string }>("/complaints", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(toApiDraft(draft))
  });
}

export async function extractDocumentText(file: File) {
  const form = new FormData();
  form.append("file", file);
  const response = await request<{ text: string }>("/documents/extract-text", { method: "POST", body: form });
  return response.text;
}

export async function askCopilot(message: string, draft: ComplaintDraft) {
  const response = await request<{ message: string; field_updates: Partial<ApiDraft> }>("/copilot/chat", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, draft: toApiDraft(draft) })
  });
  return { message: response.message, updates: toDraft({
    complaint_source: response.field_updates.complaint_source ?? draft.complaintSource,
    customer_name: response.field_updates.customer_name ?? draft.customerName,
    product_name: response.field_updates.product_name ?? draft.productName,
    product_strength: response.field_updates.product_strength ?? draft.productStrength,
    batch_number: response.field_updates.batch_number ?? draft.batchNumber,
    affected_quantity: response.field_updates.affected_quantity ?? draft.affectedQuantity,
    manufacturing_date: response.field_updates.manufacturing_date ?? draft.manufacturingDate,
    expiry_date: response.field_updates.expiry_date ?? draft.expiryDate,
    originating_site_block: response.field_updates.originating_site_block ?? draft.originatingSiteBlock,
    impacted_materials: response.field_updates.impacted_materials ?? draft.impactedMaterials,
    complaint_category: response.field_updates.complaint_category ?? draft.complaintCategory,
    complaint_description: response.field_updates.complaint_description ?? draft.complaintDescription,
    severity: response.field_updates.severity ?? draft.severity,
    suggested_next_action: response.field_updates.suggested_next_action ?? draft.suggestedNextAction,
    initial_risk_assessment: response.field_updates.initial_risk_assessment ?? draft.initialRiskAssessment
  }) };
}
