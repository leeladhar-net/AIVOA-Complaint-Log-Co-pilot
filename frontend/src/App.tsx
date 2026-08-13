import { useState, type ChangeEvent } from "react";
import { useDispatch, useSelector } from "react-redux";
import { populateDraft, setStatus, updateField } from "./features/complaints/complaintSlice";
import { analyzeComplaint as requestAnalysis, askCopilot, extractDocumentText, saveComplaint } from "./api/complaints";
import type { ChatMessage, ComplaintDraft } from "./types";
import type { RootState } from "./store";

const sampleComplaint = `Apollo Pharmacy reported 12 discolored capsules in Amoxicillin Capsules 500 mg. Batch number AMX240602. Manufacturing date March 2026. Expiry date February 2028. Please log this complaint and arrange an investigation.`;

function Field({ label, field, multiline = false }: { label: string; field: keyof ComplaintDraft; multiline?: boolean }) {
  const dispatch = useDispatch();
  const value = useSelector((state: RootState) => state.complaint.draft[field]);
  const handleChange = (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    dispatch(updateField({ field, value: event.target.value }));
  };

  return <label className={multiline ? "field field-wide" : "field"}>
    <span>{label}</span>
    {multiline
      ? <textarea value={value} onChange={handleChange} rows={4} placeholder="Awaiting AI extraction..." />
      : <input value={value} onChange={handleChange} placeholder="Awaiting AI extraction..." />}
  </label>;
}

export function App() {
  const dispatch = useDispatch();
  const { status, draft } = useSelector((state: RootState) => state.complaint);

  const fieldMappings: Record<keyof ComplaintDraft, string> = {
    complaintSource: "Complaint Source",
    customerName: "Customer Name",
    productName: "Product Name",
    productStrength: "Product Strength",
    batchNumber: "Batch / Lot Number",
    affectedQuantity: "Affected Quantity",
    manufacturingDate: "Manufacturing Date",
    expiryDate: "Expiry Date",
    originatingSiteBlock: "Originating Site Block",
    impactedMaterials: "Impacted Non-Product Materials",
    complaintCategory: "Complaint Category",
    complaintDescription: "Complaint Description",
    severity: "Severity (Suggested)",
    suggestedNextAction: "Suggested Next Action",
    initialRiskAssessment: "Initial Risk Assessment"
  };

  const totalFields = Object.keys(fieldMappings).length;
  const enteredFields = Object.keys(fieldMappings).filter(
    (key) => (draft[key as keyof ComplaintDraft] || "").trim() !== ""
  ).length;
  const percentage = Math.round((enteredFields / totalFields) * 100);

  const missingFields = Object.keys(fieldMappings).filter(
    (key) => !(draft[key as keyof ComplaintDraft] || "").trim()
  ) as Array<keyof ComplaintDraft>;

  const filledFields = Object.keys(fieldMappings).filter(
    (key) => (draft[key as keyof ComplaintDraft] || "").trim()
  ) as Array<keyof ComplaintDraft>;

  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: "welcome", role: "assistant", content: "Ready to process a new complaint. Paste a customer email or upload a complaint PDF, and I will extract the data and run an initial risk assessment." }
  ]);

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const analyzeComplaint = async () => {
    const content = prompt.trim() || sampleComplaint;
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content }]);
    setIsAnalyzing(true);
    try {
      const result = await requestAnalysis(content);
      dispatch(populateDraft(result.draft));
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: `Complaint parsed successfully using ${result.provider}. Workflow: ${result.steps.join(" → ")}. Please review the populated form before committing it.` }]);
      setPrompt("");
    } catch (error) {
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: `Analysis failed: ${error instanceof Error ? error.message : "Unknown error"}` }]);
    } finally { setIsAnalyzing(false); }
  };

  const askQuestion = async () => {
    const content = prompt.trim();
    if (!content) return;
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content }]);
    setIsAnalyzing(true);
    try {
      const result = await askCopilot(content, draft);
      const changedFields = (Object.keys(result.updates) as Array<keyof ComplaintDraft>).filter((field) => result.updates[field] !== draft[field]);
      changedFields.forEach((field) => dispatch(updateField({ field, value: result.updates[field] })));
      const updateNote = changedFields.length ? ` Updated: ${changedFields.join(", ")}.` : "";
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: `${result.message}${updateNote}` }]);
      setPrompt("");
    } catch (error) {
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: `Copilot request failed: ${error instanceof Error ? error.message : "Unknown error"}` }]);
    } finally { setIsAnalyzing(false); }
  };

  const commitComplaint = async () => {
    if (status !== "Ready to Commit") return;
    setIsSaving(true);
    try {
      const saved = await saveComplaint(draft);
      dispatch(setStatus("Committed"));
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: `Complaint ${saved.complaint_number} has been committed to the QMS ledger.` }]);
    } catch (error) {
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: `Save failed: ${error instanceof Error ? error.message : "Unknown error"}` }]);
    } finally { setIsSaving(false); }
  };

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setIsAnalyzing(true);
    try {
      const text = await extractDocumentText(file);
      setPrompt(text);
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: `Extracted text from ${file.name}. Review it in the composer, then select Analyze complaint.` }]);
    } catch (error) {
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: `Document extraction failed: ${error instanceof Error ? error.message : "Unknown error"}` }]);
    } finally { setIsAnalyzing(false); event.target.value = ""; }
  };

  return <main className="app-shell">
    <section className="complaint-panel">
      <header className="page-header">
        <div>
          <h1>Log Customer Complaint</h1>
          <p>API &amp; FDF Quality Assurance Module</p>
        </div>
        <span className={`status status-${status.toLowerCase().replace(/\s+/g, "-")}`}>{status}</span>
      </header>

      {status === "Ready to Commit" && (
        <section className="completion-widget">
          <div className="completion-header">
            <span className="completion-title">Form Completion Tracker</span>
            <span className="completion-badge">{percentage}% Completed</span>
          </div>
          <div className="completion-progress-track">
            <div className="completion-progress-bar" style={{ width: `${percentage}%` }}></div>
          </div>
          <div className="completion-details">
            <div className="field-status-column">
              <h3>Missing Fields ({missingFields.length})</h3>
              <div className="field-badges">
                {missingFields.length === 0 ? (
                  <span className="no-fields-note">All fields completed! Ready to commit.</span>
                ) : (
                  missingFields.map((key) => (
                    <span key={key} className="field-badge-missing">
                      {fieldMappings[key]}
                    </span>
                  ))
                )}
              </div>
            </div>
            <div className="field-status-column">
              <h3>Entered Fields ({filledFields.length})</h3>
              <div className="field-badges">
                {filledFields.length === 0 ? (
                  <span className="no-fields-note">Awaiting inputs...</span>
                ) : (
                  filledFields.map((key) => (
                    <span key={key} className="field-badge-filled">
                      ✓ {fieldMappings[key]}
                    </span>
                  ))
                )}
              </div>
            </div>
          </div>
        </section>
      )}

      <form onSubmit={(event) => event.preventDefault()}>
        <h2>1. Origin &amp; Customer Details</h2>
        <div className="form-grid"><Field label="Complaint Source" field="complaintSource" /><Field label="Customer Name" field="customerName" /></div>
        <h2>2. Product &amp; Batch Identification</h2>
        <div className="form-grid">
          <Field label="Product Name" field="productName" /><Field label="Product Strength" field="productStrength" />
          <Field label="Batch / Lot Number" field="batchNumber" /><Field label="Affected Quantity" field="affectedQuantity" />
          <Field label="Manufacturing Date" field="manufacturingDate" /><Field label="Expiry Date" field="expiryDate" />
        </div>
        <h2>3. Facility &amp; Material Impact</h2>
        <div className="form-grid"><Field label="Originating Site Block" field="originatingSiteBlock" /><Field label="Impacted Non-Product Materials" field="impactedMaterials" /></div>
        <h2>4. Defect Analysis</h2>
        <div className="form-grid"><Field label="Complaint Category" field="complaintCategory" /><Field label="Complaint Description" field="complaintDescription" multiline /></div>

        <section className="risk-card">
          <h2>AI Copilot Risk Assessment</h2>
          <div className="form-grid"><Field label="Severity (Suggested)" field="severity" /><Field label="Suggested Next Action" field="suggestedNextAction" /></div>
          <Field label="Initial Risk Assessment" field="initialRiskAssessment" multiline />
        </section>
        <button className="commit-button" type="button" disabled={status !== "Ready to Commit" || isSaving} onClick={commitComplaint}>{isSaving ? "Saving…" : "Commit to QMS Ledger"}</button>
      </form>
    </section>

    <aside className="copilot-panel">
      <header><h2>⚗ AIVOA Copilot</h2><p>Drop complaint files or paste text below.</p></header>
      <div className="messages">{messages.map((message) => <article key={message.id} className={`message ${message.role}`}><span>{message.content}</span></article>)}</div>
      <div className="composer">
        <label className="upload-control">📎 <input type="file" accept=".pdf,.txt" onChange={handleFile} /> Attach PDF or text file</label>
        <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Type or paste a complaint. Leave blank to run the included demo complaint." rows={4} />
        <div className="composer-actions">
          <button className="secondary-button" disabled={isAnalyzing || !prompt.trim()} onClick={askQuestion}>Ask Copilot</button>
          <button disabled={isAnalyzing} onClick={analyzeComplaint}>{isAnalyzing ? "Working…" : "Analyze complaint"}</button>
        </div>
      </div>
      <small>Powered by LangGraph (backend connection pending)</small>
    </aside>
  </main>;
}
