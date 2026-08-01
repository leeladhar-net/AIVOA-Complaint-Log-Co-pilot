export type ComplaintStatus = "Pending Triage" | "Ready to Commit" | "Committed";

export interface ComplaintDraft {
  complaintSource: string;
  customerName: string;
  productName: string;
  productStrength: string;
  batchNumber: string;
  affectedQuantity: string;
  manufacturingDate: string;
  expiryDate: string;
  originatingSiteBlock: string;
  impactedMaterials: string;
  complaintCategory: string;
  complaintDescription: string;
  severity: string;
  suggestedNextAction: string;
  initialRiskAssessment: string;
}

export interface ChatMessage {
  id: string;
  role: "assistant" | "user";
  content: string;
}
