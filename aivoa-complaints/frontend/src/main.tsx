import { StrictMode, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Provider, useDispatch, useSelector } from 'react-redux'
import { configureStore, createSlice, type PayloadAction } from '@reduxjs/toolkit'
import './styles.css'

type Severity = 'Minor' | 'Major' | 'Critical' | ''
type Priority = 'Low' | 'Medium' | 'High' | 'Critical' | ''
type Complaint = Record<string, string> & { initial_severity: Severity; priority: Priority; status: string }
type Risk = { severity: string; priority: string; rationale: string; suggested_action: string; risk_mitigation: string[]; preventive_actions: string[] } | null
type ChatTurn = { role: 'user' | 'assistant'; content: string }
type DuplicateMatch = { complaint_number: string; customer_name?: string; product_name?: string; batch_lot_number?: string; complaint_type?: string; reason: string; notification_note: string }
type Change = { field: string; before: string; after: string; by: 'You' | 'Copilot'; time: string }

const empty: Complaint = { complaint_source: '', customer_name: '', product_name: '', product_strength: '', batch_lot_number: '', manufacturing_date: '', expiry_date: '', quantity_affected: '', complaint_type: '', complaint_date: '', detailed_description: '', initial_severity: '', priority: '', status: 'Pending Triage' }
const slice = createSlice({
  name: 'complaint',
  initialState: { draft: empty, sourceText: '', summary: '', risk: null as Risk, duplicates: [] as DuplicateMatch[], warnings: [] as string[], loading: false, riskLoading: false, saved: '', error: '' },
  reducers: {
    patch(s, a: PayloadAction<Partial<Complaint>>) { s.draft = { ...s.draft, ...a.payload } as Complaint },
    setSource(s, a: PayloadAction<string>) { s.sourceText = a.payload },
    setResult(s, a: PayloadAction<any>) { s.draft = { ...empty, ...a.payload.complaint, manufacturing_date: a.payload.complaint.manufacturing_date || '', expiry_date: a.payload.complaint.expiry_date || '', complaint_date: a.payload.complaint.complaint_date || '' }; s.summary = a.payload.summary; s.risk = null; s.warnings = a.payload.warnings },
    setLoading(s, a: PayloadAction<boolean>) { s.loading = a.payload },
    setRiskLoading(s, a: PayloadAction<boolean>) { s.riskLoading = a.payload },
    setRisk(s, a: PayloadAction<Risk>) { s.risk = a.payload },
    setDuplicates(s, a: PayloadAction<DuplicateMatch[]>) { s.duplicates = a.payload },
    setError(s, a: PayloadAction<string>) { s.error = a.payload },
    setSaved(s, a: PayloadAction<string>) { s.saved = a.payload },
    reset(s) { Object.assign(s, { draft: empty, sourceText: '', summary: '', risk: null, duplicates: [], warnings: [], loading: false, riskLoading: false, saved: '', error: '' }) }
  }
})
const store = configureStore({ reducer: { complaint: slice.reducer } })
type Root = ReturnType<typeof store.getState>
const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
const fields = [['complaint_source', 'Complaint Source'], ['customer_name', 'Customer Name'], ['product_name', 'Product Name'], ['product_strength', 'Product Strength / Grade'], ['batch_lot_number', 'Batch/Lot Number'], ['manufacturing_date', 'Manufacturing Date'], ['expiry_date', 'Expiry Date'], ['quantity_affected', 'Quantity Affected'], ['complaint_type', 'Complaint Type'], ['complaint_date', 'Complaint Date']]
const apiMessage = (detail: unknown, fallback: string) => typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((item: any) => item.msg || 'Invalid input').join('. ') : fallback

function App() {
  const dispatch = useDispatch()
  const state = useSelector((s: Root) => s.complaint)
  const [file, setFile] = useState<File | null>(null)
  const [message, setMessage] = useState('')
  const [chat, setChat] = useState<ChatTurn[]>([])
  const [asking, setAsking] = useState(false)
  const [changes, setChanges] = useState<Change[]>([])
  const [changedFields, setChangedFields] = useState<string[]>([])

  function recordChanges(updates: Record<string, string>, by: Change['by']) {
    const entries = Object.entries(updates).filter(([field, value]) => (state.draft[field] || '') !== value)
    if (!entries.length) return
    setChanges(current => [...entries.map(([field, after]) => ({ field, before: state.draft[field] || '', after, by, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) })), ...current])
    setChangedFields(current => [...new Set([...current, ...entries.map(([field]) => field)])])
    window.setTimeout(() => setChangedFields(current => current.filter(field => !entries.some(([changedField]) => changedField === field))), 1300)
  }

  async function findDuplicates(draft: Complaint) {
    try {
      const response = await fetch(`${API}/duplicates/check`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(draft) })
      const data = await response.json()
      if (response.ok) dispatch(slice.actions.setDuplicates(data.matches || []))
    } catch { /* Duplicate check is non-blocking; saving and intake can continue. */ }
  }

  async function analyze() {
    const source = message.trim()
    if (!file && !source) { dispatch(slice.actions.setError('Type complaint information or attach a document first.')); return }
    const hasExistingComplaint = Boolean(state.draft.customer_name || state.draft.product_name || state.draft.detailed_description)
    if (hasExistingComplaint && !file) { await applyCopilotUpdate(source); return }
    dispatch(slice.actions.setError('')); dispatch(slice.actions.setLoading(true))
    try {
      const body = new FormData()
      const userMessage = file ? `Attached ${file.name} for complaint registration.` : source
      setChat(current => [...current, { role: 'user', content: userMessage }])
      if (file) body.append('file', file); else body.append('text', source)
      const response = await fetch(`${API}/intake/analyze`, { method: 'POST', body })
      const data = await response.json()
      if (!response.ok) throw new Error(apiMessage(data.detail, 'Analysis failed'))
      dispatch(slice.actions.setResult(data))
      await findDuplicates(data.complaint)
      dispatch(slice.actions.setSource(file ? `Attached document: ${file.name}` : source))
      setMessage(''); setFile(null)
      setChat(current => [...current, { role: 'assistant', content: 'I updated the complaint log from the supplied information. Review the fields, then run the separate Risk Analyzer when ready.' }])
    } catch (error: any) { dispatch(slice.actions.setError(error.message || 'Analysis failed')) }
    finally { dispatch(slice.actions.setLoading(false)) }
  }

  async function applyCopilotUpdate(current: string) {
    setMessage(''); setChat(turns => [...turns, { role: 'user', content: current }]); setAsking(true)
    try {
      const response = await fetch(`${API}/copilot/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ complaint: state.draft, question: current }) })
      const data = await response.json()
      if (!response.ok) throw new Error(apiMessage(data.detail, 'The Copilot could not apply this update.'))
      const updates = data.field_updates && typeof data.field_updates === 'object' ? data.field_updates : {}
      if (Object.keys(updates).length) { recordChanges(updates, 'Copilot'); dispatch(slice.actions.patch(updates)); await findDuplicates({ ...state.draft, ...updates }) }
      const note = Object.keys(updates).length ? ` Updated only: ${Object.keys(updates).join(', ')}.` : ''
      setChat(turns => [...turns, { role: 'assistant', content: `${data.answer}${note}` }])
    } catch (error: any) { setChat(turns => [...turns, { role: 'assistant', content: `Copilot error: ${error.message || 'The Copilot is unavailable.'}` }]) }
    finally { setAsking(false) }
  }

  async function save() {
    dispatch(slice.actions.setError(''))
    try {
      const cleanDraft = Object.fromEntries(Object.entries(state.draft).map(([key, value]) => [key, key.includes('date') && value === '' ? null : value]))
      const payload = { ...cleanDraft, ai_summary: state.summary, risk_rationale: state.risk?.rationale, source_text: state.sourceText }
      const response = await fetch(`${API}/complaints`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      const data = await response.json()
      if (!response.ok) throw new Error(apiMessage(data.detail, 'Unable to save'))
      dispatch(slice.actions.setSaved(data.complaint_number))
    } catch (error: any) { dispatch(slice.actions.setError(error.message || 'Unable to save')) }
  }

  async function runRiskAnalysis() {
    dispatch(slice.actions.setError('')); dispatch(slice.actions.setRiskLoading(true))
    try {
      const response = await fetch(`${API}/risk/analyze`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ complaint: state.draft }) })
      const data = await response.json()
      if (!response.ok) throw new Error(apiMessage(data.detail, 'Risk analysis failed'))
      dispatch(slice.actions.setRisk(data))
    } catch (error: any) { dispatch(slice.actions.setError(error.message || 'Risk analysis failed')) }
    finally { dispatch(slice.actions.setRiskLoading(false)) }
  }

  const change = (key: string, value: string) => { recordChanges({ [key]: value }, 'You'); dispatch(slice.actions.patch({ [key]: value })) }
  const resetForm = () => { dispatch(slice.actions.reset()); setChat([]); setMessage(''); setFile(null); setChanges([]); setChangedFields([]); setAsking(false) }
  return <main>
    <header><div className="brand"><span className="spark">AI</span><div><b>AIVOA</b><small>QUALITY INTELLIGENCE</small></div></div><div className="secure">Secure QA workspace</div></header>
    <section className="hero"><div><p className="eyebrow">CUSTOMER COMPLAINTS / NEW RECORD</p><h1>Log Customer Complaint</h1><p>AI-assisted intake for pharmaceutical quality teams. Review all suggestions before saving.</p></div><span className="badge">{state.draft.status}</span></section>
    {state.error && <div className="alert error">{state.error}</div>}{state.saved && <div className="alert success">Complaint <b>{state.saved}</b> has been saved successfully.</div>}
    <div className="layout"><section className="form-card"><div className="card-title"><div><h2>Complaint record</h2><p>AI-managed log. Request any correction through the Copilot chat.</p></div><span>Copilot editing only</span></div>
      <div className="form-grid">{fields.map(([key, label]) => <label className={changedFields.includes(key) ? 'field-changed' : ''} key={key}>{label}<input type={key.includes('date') ? 'date' : 'text'} value={state.draft[key] || ''} placeholder="Awaiting AI extraction..." disabled /></label>)}</div>
      <div className="section-label">Complaint details</div><label className={changedFields.includes('detailed_description') ? 'field-changed' : ''}>Detailed Complaint Description<textarea value={state.draft.detailed_description} placeholder="Awaiting AI extraction..." disabled /></label>
      <div className="form-grid"><label className={changedFields.includes('initial_severity') ? 'field-changed' : ''}>Initial Severity<select value={state.draft.initial_severity} disabled><option value="">Select severity</option><option>Minor</option><option>Major</option><option>Critical</option></select></label><label className={changedFields.includes('priority') ? 'field-changed' : ''}>Priority<select value={state.draft.priority} disabled><option value="">Select priority</option><option>Low</option><option>Medium</option><option>High</option><option>Critical</option></select></label></div>
      {state.duplicates.length > 0 && <section className="duplicate-alert"><b>Possible duplicate complaint</b><p>This looks similar to {state.duplicates.map(match => match.complaint_number).join(', ')}. A duplicate alert will be stored when you save.</p>{state.duplicates.map(match => <div key={match.complaint_number}><b>{match.complaint_number}</b> — {match.reason}<small>{match.notification_note}</small></div>)}</section>}
      {changes.length > 0 && <section className="change-log"><div><b>Log change history</b><span>Green fields have been changed</span></div>{changes.slice(0, 5).map((entry, index) => <p key={`${entry.field}-${index}`}><b>{entry.by}</b> changed <b>{entry.field.replaceAll('_', ' ')}</b> from “{entry.before || 'blank'}” to “{entry.after}” at {entry.time}.</p>)}</section>}
      <section className="risk-analyzer"><div><p className="eyebrow">INDEPENDENT QA CHECK</p><h2>Risk Analyzer</h2><p>Evaluates the current reviewed complaint record. It does not change your log fields.</p></div><button className="analyze" type="button" onClick={runRiskAnalysis} disabled={state.riskLoading}>{state.riskLoading ? 'Assessing risk...' : 'Run Risk Analysis'}</button>{state.risk && <div className="risk"><div><b>Risk assessment</b><span className={`risk-${state.risk.priority.toLowerCase()}`}>{state.risk.priority} / {state.risk.severity}</span></div><p>{state.risk.rationale}</p><small><b>Suggested next step:</b> {state.risk.suggested_action}</small><div className="risk-guidance"><b>How to minimize the risk</b><ul>{state.risk.risk_mitigation.map(item => <li key={item}>{item}</li>)}</ul><b>How to prevent recurrence</b><ul>{state.risk.preventive_actions.map(item => <li key={item}>{item}</li>)}</ul></div></div>}</section>
      <footer className="form-actions"><button className="secondary" type="button" onClick={resetForm}>Reset form</button><button className="primary" type="button" onClick={save}>Save complaint</button></footer>
    </section>
    <aside className="ai-card"><div className="ai-heading"><span className="spark">AI</span><div><h2>AIVOA Copilot</h2><p>Register a customer complaint by chatting naturally</p></div><span className="beta">BETA</span></div>
      <div className="chat-log">{chat.length ? chat.map((turn, index) => <p className={`chat-turn ${turn.role}`} key={index}><b>{turn.role === 'user' ? 'You' : 'AIVOA'}:</b> {turn.content}</p>) : <p className="chat-turn assistant"><b>AIVOA:</b> Tell me what happened. Include any details you know, such as customer, product, batch number, quantity, and issue. I will register the complaint and fill the form for your review.</p>}{(state.loading || asking) && <div className="typing" aria-label="AIVOA is typing"><i></i><i></i><i></i></div>}</div>
      <div className="chat-composer">
        {file && <small className="file-name">Attached: {file.name}</small>}
        <div className="chat-input-row">
          <label className="attach-file" title="Attach complaint document" aria-label="Attach complaint document">+
            <input type="file" accept=".pdf,.docx,.txt,.eml" onChange={event => setFile(event.target.files?.[0] || null)} />
          </label>
          <textarea rows={1} value={message} placeholder="Describe the customer complaint..." onChange={event => setMessage(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); analyze() } }} disabled={state.loading || asking} />
          <button className="send-tick" type="button" title="Send message" aria-label="Send message" onClick={analyze} disabled={state.loading || asking || (!message.trim() && !file)}>{state.loading || asking ? '...' : '✓'}</button>
        </div>
      </div>
      {state.summary && <div className="result"><b>Copilot summary</b><p>{state.summary}</p></div>}{state.warnings.length > 0 && <div className="warnings"><b>Needs review</b>{state.warnings.map(warning => <p key={warning}>- {warning}</p>)}</div>}
    </aside></div>
  </main>
}

createRoot(document.getElementById('root')!).render(<StrictMode><Provider store={store}><App /></Provider></StrictMode>)
