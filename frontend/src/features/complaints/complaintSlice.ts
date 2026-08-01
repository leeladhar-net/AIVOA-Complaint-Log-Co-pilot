import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { ComplaintDraft, ComplaintStatus } from "../../types";

const initialDraft: ComplaintDraft = {
  complaintSource: "",
  customerName: "",
  productName: "",
  productStrength: "",
  batchNumber: "",
  affectedQuantity: "",
  manufacturingDate: "",
  expiryDate: "",
  originatingSiteBlock: "",
  impactedMaterials: "",
  complaintCategory: "",
  complaintDescription: "",
  severity: "",
  suggestedNextAction: "",
  initialRiskAssessment: ""
};

const complaintSlice = createSlice({
  name: "complaint",
  initialState: { draft: initialDraft, status: "Pending Triage" as ComplaintStatus },
  reducers: {
    updateField: (state, action: PayloadAction<{ field: keyof ComplaintDraft; value: string }>) => {
      state.draft[action.payload.field] = action.payload.value;
    },
    populateDraft: (state, action: PayloadAction<ComplaintDraft>) => {
      state.draft = action.payload;
      state.status = "Ready to Commit";
    },
    setStatus: (state, action: PayloadAction<ComplaintStatus>) => {
      state.status = action.payload;
    }
  }
});

export const { updateField, populateDraft, setStatus } = complaintSlice.actions;
export default complaintSlice.reducer;
