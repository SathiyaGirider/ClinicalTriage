import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, post } from "../shared/api";
import { AlertTriangleIcon, CheckIcon, FlagIcon, ShieldAlertIcon } from "../shared/icons";
import { Banner, Button, Card, Dialog, EmptyState, ErrorBox, Loading, StatusPill, useToast } from "../shared/ui";

type Rx = { drug: string; dose: string; frequency: string; duration: string; instructions: string };
const emptyRx = (): Rx => ({ drug: "", dose: "", frequency: "", duration: "", instructions: "" });

type WS = {
  patient: { id: number; full_name: string; age: string; language: string };
  appointment: { id: number; status: string; token_label: string | null; date: string } | null;
  entry: { priority: string | null; priority_rationale: string | null; decided_by: string | null; audit_notes: string[]; chief_complaint?: string } | null;
  summary: { id?: number; priority: string; priority_rationale: string; decided_by: string | null; audit_notes: string[]; input_confidence: string | null } | null;
  lines: string[];
  answers: any;
  vitals: any;
  history: { own: any[]; shared: any[]; shared_label: string | null; consent: boolean };
};

const NOTE_TEXT: Record<string, string> = {
  injection_suspected: "Instruction-like text detected (escalated; safety rules ran on original text)",
  low_input_confidence: "Low input confidence (patient unsure or vague)",
  llm_fallback_used: "AI estimate unavailable or unsure: fail-safe used",
  ai_unavailable_escalated: "AI unavailable: escalated for safety",
  fallback_mild_allowlist: "Deterministic fallback: mild allowlist (routine)",
  output_filtered: "AI text was filtered for diagnosis/medication language",
  patient_reported_worse_at_checkin: "Patient reported symptoms became worse at check-in",
  patient_reported_new_symptom_at_checkin: "Patient reported a new symptom at check-in",
  patient_reported_change: "Patient reported a change since booking",
  recheck_addendum: "Short clinical re-check added",
  not_pre_screened: "Patient opted out of automated questions (nurse check-in required)",
};

export default function Workspace() {
  const { patientId } = useParams();
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const { showToast } = useToast();

  const [ws, setWs] = useState<WS | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [dx, setDx] = useState({ text: "", code: "", notes: "", follow: "" });
  const [rx, setRx] = useState<Rx[]>([emptyRx()]);
  const [busy, setBusy] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // UI view state
  const [expandedSummary, setExpandedSummary] = useState(false);

  // Dialog states
  const [showOverrideDialog, setShowOverrideDialog] = useState(false);
  const [overridePriority, setOverridePriority] = useState<"emergency" | "same-day" | "routine">("same-day");
  const [overrideReason, setOverrideReason] = useState("");

  const [showConsentReqDialog, setShowConsentReqDialog] = useState(false);
  const [reqPurpose, setReqPurpose] = useState("Care and treatment");
  const [reqHiTypes, setReqHiTypes] = useState<string[]>(["OPConsultNote", "Prescription"]);

  const [showCompleteDialog, setShowCompleteDialog] = useState(false);

  // Staff Feedback state
  const [feedbackGiven, setFeedbackGiven] = useState<boolean | null>(null);
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [feedbackUseful, setFeedbackUseful] = useState(true);
  const [feedbackReason, setFeedbackReason] = useState("");

  const appt = sp.get("appointment");

  const load = () =>
    api<WS>(`/doctor/patient/${patientId}${appt ? `?appointment_id=${appt}` : ""}`)
      .then((data) => {
        setWs(data);
        setErr(null);
      })
      .catch(setErr);

  useEffect(() => {
    load();
  }, [patientId, appt]);

  const handleOverrideSubmit = async () => {
    if (!ws?.appointment || !overrideReason.trim()) return;
    setBusy(true);
    try {
      await post("/doctor/override", {
        appointment_id: ws.appointment.id,
        priority: overridePriority,
        reason: overrideReason.trim(),
      });
      setShowOverrideDialog(false);
      setOverrideReason("");
      showToast("Priority updated successfully", "success");
      load();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };

  const handleConsentRequestSubmit = async () => {
    if (!ws) return;
    setBusy(true);
    try {
      const today = new Date().toISOString().split("T")[0];
      const pastYear = new Date(Date.now() - 365 * 86400000).toISOString().split("T")[0];
      await post("/abdm/consent/request", {
        patient_id: ws.patient.id,
        purpose: reqPurpose,
        hi_types: reqHiTypes,
        date_from: pastYear,
        date_to: today,
        duration_hours: 24,
      });
      setShowConsentReqDialog(false);
      showToast("Consent request sent to patient's app", "info");
      load();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };

  const handleFeedbackSubmit = async () => {
    if (!ws?.summary?.id && !ws?.appointment?.id) {
      setShowFeedbackModal(false);
      setFeedbackGiven(feedbackUseful);
      return;
    }
    setBusy(true);
    try {
      await post("/pipeline/feedback", {
        summary_id: ws.summary?.id || ws.appointment?.id || 1,
        useful: feedbackUseful,
        reason: feedbackReason.trim() || undefined,
      });
      setFeedbackGiven(feedbackUseful);
      setShowFeedbackModal(false);
      setFeedbackReason("");
      showToast("Thank you for your feedback", "success");
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };

  const handleCompleteConsultation = async () => {
    if (!ws?.appointment) return;
    setBusy(true);
    try {
      await post("/ehr/consultation", {
        appointment_id: ws.appointment.id,
        diagnosis_text: dx.text.trim(),
        diagnosis_code: dx.code.trim() || undefined,
        clinical_notes: dx.notes.trim(),
        prescription: rx.filter((r) => r.drug.trim()),
        follow_up_date: dx.follow || undefined,
      });
      showToast("Consultation completed and saved to EHR", "success");
      nav("/staff/doctor");
    } catch (ex) {
      setErr(ex);
    } finally {
      setBusy(false);
      setShowCompleteDialog(false);
    }
  };

  if (!ws) return err ? <ErrorBox error={err} onRetry={load} /> : <Loading />;

  const notes = Array.from(new Set([...(ws.summary?.audit_notes ?? []), ...(ws.entry?.audit_notes ?? [])]));
  const open = ws.appointment && !["completed", "cancelled", "no_show"].includes(ws.appointment.status);
  const setR = (i: number, k: keyof Rx, v: string) => {
    setHasChanges(true);
    setRx(rx.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  };

  const priorityVal = ws.summary?.priority || ws.entry?.priority || "routine";
  const chiefComplaint = ws.answers?.your_words || ws.entry?.chief_complaint || "Routine evaluation";

  return (
    <div>
      {/* Patient Workspace Top Bar */}
      <div className="spread" style={{ marginBottom: "1rem", alignItems: "flex-start" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: "1.6rem" }}>
            {ws.patient.full_name} · Age {ws.patient.age || "—"} {ws.appointment?.token_label ? `· Token ${ws.appointment.token_label}` : ""}
          </h1>
          <div className="small-text muted" style={{ marginTop: 4 }}>
            Status: <strong>{ws.appointment?.status ?? "Active Visit"}</strong> · Language: {ws.patient.language?.toUpperCase() || "EN"}
          </div>
        </div>
        <div className="row" style={{ gap: "0.5rem" }}>
          {ws.appointment && (
            <Button
              variant="outline"
              size="small"
              onClick={() => {
                setOverridePriority(priorityVal as any);
                setShowOverrideDialog(true);
              }}
            >
              Change priority
            </Button>
          )}
        </div>
      </div>

      <ErrorBox error={err} />

      {/* One-Line Headline Bar (Collapsible) */}
      <div className="card" style={{ padding: "0.85rem 1rem", marginBottom: "1rem", borderLeft: `4px solid ${priorityVal === "emergency" ? "var(--status-emergency-solid)" : priorityVal === "same-day" ? "var(--status-urgent-solid)" : "var(--status-routine-solid)"}` }}>
        <div className="spread" style={{ alignItems: "center" }}>
          <div className="row" style={{ alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
            <StatusPill
              variant={priorityVal as any}
              label={priorityVal.toUpperCase()}
              icon={priorityVal === "emergency" ? <ShieldAlertIcon width={14} height={14} /> : priorityVal === "same-day" ? <AlertTriangleIcon width={14} height={14} /> : <CheckIcon width={14} height={14} />}
            />
            <span style={{ fontWeight: 600 }}>Chief Complaint:</span>
            <span>{chiefComplaint}</span>
          </div>
          <Button
            variant="ghost"
            size="small"
            onClick={() => setExpandedSummary((x) => !x)}
            aria-expanded={expandedSummary}
          >
            {expandedSummary ? "Collapse summary ▲" : "View full summary ▼"}
          </Button>
        </div>
      </div>

      <div className="staff-grid">
        {/* Left Column: Triage & Decision Support + Consultation Form */}
        <div>
          {/* Expanded Summary: Two Clearly Separated Blocks */}
          {expandedSummary && (
            <div style={{ marginBottom: "1.5rem" }}>
              {/* Block 1: What the Patient Told Us */}
              <Card className="mb-2">
                <h2 style={{ fontSize: "1.1rem", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "0.4rem", marginBottom: "0.75rem" }}>
                  What the patient told us
                </h2>
                {ws.answers ? (
                  <div>
                    <p style={{ margin: "0 0 0.5rem" }}>
                      <em>“{ws.answers.your_words || ws.entry?.chief_complaint || "No verbal details recorded."}”</em>
                    </p>
                    {ws.answers.follow_up_answers && Object.keys(ws.answers.follow_up_answers).length > 0 && (
                      <div className="small-text" style={{ marginTop: "0.5rem" }}>
                        <strong>Answers given:</strong>
                        <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.2rem" }}>
                          {Object.entries(ws.answers.follow_up_answers).map(([k, v]) => (
                            <li key={k}>{k}: {String(v)}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {ws.answers.safety_screen && ws.answers.safety_screen.length > 0 && (
                      <div className="small-text" style={{ marginTop: "0.4rem" }}>
                        <strong>Safety screen:</strong> {ws.answers.safety_screen.join(", ")}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="muted small-text">No intake answers recorded for this appointment.</p>
                )}
              </Card>

              {/* Block 2: Decision Support (AI-assisted). Confirm before acting. */}
              <Card className="mb-2">
                <div className="spread">
                  <h2 style={{ fontSize: "1.1rem", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "0.4rem", marginBottom: "0.75rem", flex: 1 }}>
                    Decision support (AI-assisted). Confirm before acting.
                  </h2>
                </div>

                <div style={{ marginBottom: "0.5rem" }}>
                  <strong>Priority Rationale:</strong> {ws.summary?.priority_rationale || ws.entry?.priority_rationale || "Evaluated by safety rules."}
                </div>

                <div className="row small-text muted" style={{ gap: "1rem", marginBottom: "0.5rem" }}>
                  <span>Source: <strong>{ws.summary?.decided_by === "rule" ? "Fixed Safety Rule" : ws.summary?.decided_by === "fallback" ? "Fail-Safe Fallback" : ws.summary?.decided_by === "human" ? "Staff Override" : "AI-Assisted"}</strong></span>
                  {ws.summary?.input_confidence && <span>Input Confidence: <strong>{ws.summary.input_confidence}</strong></span>}
                </div>

                {/* Vitals in decision support */}
                {ws.vitals && (
                  <div className="notice small-text" style={{ margin: "0.5rem 0" }}>
                    <strong>Vitals:</strong> BP {ws.vitals.bp_sys ?? "-"}/{ws.vitals.bp_dia ?? "-"} mmHg · Temp {ws.vitals.temp_c ?? "-"} °C · SpO2 {ws.vitals.spo2 ?? "-"}% · Pulse {ws.vitals.pulse ?? "-"} bpm
                  </div>
                )}

                {/* Audit trail notes */}
                {notes.length > 0 && (
                  <div className="notice small-text" style={{ margin: "0.5rem 0" }}>
                    <strong>Clinical & Safety Notes:</strong>
                    <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.2rem" }}>
                      {notes.map((n) => (
                        <li key={n}>{NOTE_TEXT[n] ?? n.replace(/_/g, " ")}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* ICMR One-Tap Staff Feedback Control */}
                <div style={{ marginTop: "1rem", paddingTop: "0.75rem", borderTop: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span className="small-text muted">Was this decision support summary useful?</span>
                  {feedbackGiven !== null ? (
                    <span className="small-text pill ok">Feedback recorded ({feedbackGiven ? "Useful" : "Not useful"})</span>
                  ) : (
                    <div className="row" style={{ gap: "0.4rem" }}>
                      <Button
                        variant="ghost"
                        size="small"
                        onClick={() => {
                          setFeedbackUseful(true);
                          setShowFeedbackModal(true);
                        }}
                      >
                        👍 Useful
                      </Button>
                      <Button
                        variant="ghost"
                        size="small"
                        onClick={() => {
                          setFeedbackUseful(false);
                          setShowFeedbackModal(true);
                        }}
                      >
                        👎 Not useful
                      </Button>
                    </div>
                  )}
                </div>
              </Card>
            </div>
          )}

          {/* Consultation Form (Physician Authored Only) */}
          {open ? (
            <form
              className="card"
              onSubmit={(e) => {
                e.preventDefault();
                setShowCompleteDialog(true);
              }}
            >
              <div className="spread">
                <h2>Clinical Consultation</h2>
                {hasChanges && <span className="small-text pill warn">Unsaved changes</span>}
              </div>
              <p className="muted small-text">
                All fields are typed and authorized by the treating physician only. Zero AI autofill or diagnosis suggestions.
              </p>

              <label className="field">
                Diagnosis (Physician Assessment) *
                <input
                  value={dx.text}
                  onChange={(e) => {
                    setHasChanges(true);
                    setDx({ ...dx, text: e.target.value });
                  }}
                  required
                  maxLength={500}
                  autoComplete="off"
                  placeholder="e.g. Acute streptococcal pharyngitis"
                />
              </label>

              <label className="field">
                ICD-10 Code (Optional)
                <input
                  value={dx.code}
                  onChange={(e) => {
                    setHasChanges(true);
                    setDx({ ...dx, code: e.target.value });
                  }}
                  maxLength={20}
                  autoComplete="off"
                  placeholder="e.g. J02.0"
                />
              </label>

              <label className="field">
                Clinical Examination & Notes
                <textarea
                  value={dx.notes}
                  onChange={(e) => {
                    setHasChanges(true);
                    setDx({ ...dx, notes: e.target.value });
                  }}
                  maxLength={5000}
                  placeholder="Physical exam findings, investigations ordered, clinical impression..."
                />
              </label>

              <h3>Prescriptions</h3>
              {rx.map((r, i) => (
                <div className="rx-row" key={i}>
                  <label>
                    Medicine *
                    <input
                      value={r.drug}
                      onChange={(e) => setR(i, "drug", e.target.value)}
                      autoComplete="off"
                      placeholder="e.g. Amoxicillin"
                    />
                  </label>
                  <label>
                    Dose
                    <input
                      value={r.dose}
                      onChange={(e) => setR(i, "dose", e.target.value)}
                      autoComplete="off"
                      placeholder="500 mg"
                    />
                  </label>
                  <label>
                    Frequency
                    <input
                      value={r.frequency}
                      onChange={(e) => setR(i, "frequency", e.target.value)}
                      autoComplete="off"
                      placeholder="Three times a day"
                    />
                  </label>
                  <label>
                    Duration
                    <input
                      value={r.duration}
                      onChange={(e) => setR(i, "duration", e.target.value)}
                      autoComplete="off"
                      placeholder="5 days"
                    />
                  </label>
                  <label>
                    Instructions
                    <input
                      value={r.instructions}
                      onChange={(e) => setR(i, "instructions", e.target.value)}
                      autoComplete="off"
                      placeholder="After food"
                    />
                  </label>
                  <Button
                    type="button"
                    variant="ghost"
                    size="small"
                    onClick={() => {
                      setHasChanges(true);
                      setRx(rx.filter((_, j) => j !== i));
                    }}
                    aria-label="Remove prescription row"
                  >
                    ✕
                  </Button>
                </div>
              ))}
              <Button
                type="button"
                variant="outline"
                size="small"
                onClick={() => setRx([...rx, emptyRx()])}
                style={{ marginBottom: "1rem" }}
              >
                + Add medicine
              </Button>

              <label className="field">
                Follow-up Date
                <input
                  type="date"
                  value={dx.follow}
                  onChange={(e) => {
                    setHasChanges(true);
                    setDx({ ...dx, follow: e.target.value });
                  }}
                />
              </label>

              <Button
                type="submit"
                variant="primary"
                className="block"
                style={{ marginTop: "1rem" }}
                disabled={!dx.text.trim()}
              >
                Complete Consultation
              </Button>
            </form>
          ) : (
            <Card>
              <h3>Visit Finalized</h3>
              <p className="muted">This visit is currently marked as <strong>{ws.appointment?.status ?? "completed"}</strong>.</p>
            </Card>
          )}
        </div>

        {/* Right Column: Encounters History & ABDM Outside Access */}
        <div className="panel">
          <h2>Patient History</h2>

          {/* Section A: Your Encounters */}
          <h3>Your Encounters (Authored by you)</h3>
          {ws.history.own.length === 0 ? (
            <p className="muted small-text">No prior encounters authored by you for this patient.</p>
          ) : (
            ws.history.own.map((e) => (
              <div className="entry" key={e.id}>
                <div className="spread">
                  <strong>{e.date}</strong>
                  <StatusPill variant="routine" label="Own Record" />
                </div>
                <div style={{ margin: "0.25rem 0" }}>
                  <strong>{e.diagnosis_text}</strong> {e.diagnosis_code ? `(${e.diagnosis_code})` : ""}
                </div>
                {e.clinical_notes && <div className="small-text muted">Notes: {e.clinical_notes}</div>}
                {e.prescriptions && e.prescriptions.length > 0 && (
                  <div className="small-text" style={{ marginTop: "0.4rem" }}>
                    {e.prescriptions.map((p: Rx, i: number) => (
                      <div key={i}>℞ {p.drug} {p.dose} · {p.frequency} · {p.duration}</div>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}

          {/* Section B: Outside Doctors (ABDM Consent Request Simulation) */}
          <div style={{ marginTop: "2rem", borderTop: "1px solid var(--border-subtle)", paddingTop: "1rem" }}>
            <div className="spread">
              <h3>Outside History (ABDM Simulation)</h3>
              <StatusPill variant="neutral" label="Simulated Gateway" />
            </div>

            {!ws.history.consent && ws.history.shared.length === 0 ? (
              <div className="card" style={{ marginTop: "0.5rem" }}>
                <p className="muted small-text">
                  Outside records from other facilities are protected. Access requires time-bound patient consent through ABDM.
                </p>
                <Button
                  variant="primary"
                  size="small"
                  onClick={() => setShowConsentReqDialog(true)}
                >
                  Request access to history
                </Button>
              </div>
            ) : (
              <>
                <Banner variant="routine" className="mb-2">
                  Shared via approved ABDM consent. Diagnoses only.
                </Banner>
                {ws.history.shared.length === 0 ? (
                  <p className="muted small-text">No prior outside records found within approved consent scope.</p>
                ) : (
                  ws.history.shared.map((e) => (
                    <div className="entry" key={e.id}>
                      <div className="spread">
                        <strong>{e.date}</strong>
                        <span className="small-text muted">{e.specialty} · {e.hospital_name}</span>
                      </div>
                      <div style={{ marginTop: "0.25rem" }}>{e.diagnosis_text}</div>
                    </div>
                  ))
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Override Priority Dialog */}
      <Dialog
        open={showOverrideDialog}
        onClose={() => setShowOverrideDialog(false)}
        title="Physician Priority Override"
        confirmLabel="Apply Priority"
        confirmVariant="primary"
        onConfirm={handleOverrideSubmit}
        busy={busy}
      >
        <p className="small-text muted">
          Clinical decision support priority can be altered with a documented clinical rationale. All overrides are logged for audit.
        </p>
        <label className="field" style={{ marginTop: "1rem" }}>
          Target Priority:
          <select
            value={overridePriority}
            onChange={(e) => setOverridePriority(e.target.value as any)}
          >
            <option value="routine">Routine</option>
            <option value="same-day">Same-day (Urgent)</option>
            <option value="emergency">Emergency</option>
          </select>
        </label>
        <label className="field" style={{ marginTop: "1rem" }}>
          Clinical Reason (Required) *
          <input
            value={overrideReason}
            onChange={(e) => setOverrideReason(e.target.value)}
            placeholder="e.g. Signs of atypical angina upon clinical observation"
            required
            maxLength={300}
          />
        </label>
      </Dialog>

      {/* ABDM Consent Request Dialog */}
      <Dialog
        open={showConsentReqDialog}
        onClose={() => setShowConsentReqDialog(false)}
        title="Request Outside Medical History (ABDM)"
        confirmLabel="Send Request to Patient"
        confirmVariant="primary"
        onConfirm={handleConsentRequestSubmit}
        busy={busy}
      >
        <p className="small-text muted">
          Send an electronic consent request to the patient's LifeLine app. Records will only become accessible once the patient approves.
        </p>
        <label className="field" style={{ marginTop: "1rem" }}>
          Purpose of Access:
          <input
            value={reqPurpose}
            onChange={(e) => setReqPurpose(e.target.value)}
            placeholder="Care and treatment"
            required
            maxLength={120}
          />
        </label>
        <div style={{ marginTop: "1rem" }}>
          <span className="field-label-text">Requested Health Information Types:</span>
          <div className="row" style={{ gap: "1rem", marginTop: "0.5rem" }}>
            <label className="row" style={{ gap: "0.4rem" }}>
              <input
                type="checkbox"
                checked={reqHiTypes.includes("OPConsultNote")}
                onChange={(e) =>
                  setReqHiTypes((prev) =>
                    e.target.checked ? [...prev, "OPConsultNote"] : prev.filter((x) => x !== "OPConsultNote")
                  )
                }
              />
              <span>OP Consultation Note (Diagnoses)</span>
            </label>
            <label className="row" style={{ gap: "0.4rem" }}>
              <input
                type="checkbox"
                checked={reqHiTypes.includes("Prescription")}
                onChange={(e) =>
                  setReqHiTypes((prev) =>
                    e.target.checked ? [...prev, "Prescription"] : prev.filter((x) => x !== "Prescription")
                  )
                }
              />
              <span>Prescriptions</span>
            </label>
          </div>
        </div>
      </Dialog>

      {/* Staff Feedback Dialog */}
      <Dialog
        open={showFeedbackModal}
        onClose={() => setShowFeedbackModal(false)}
        title={`Decision Support Feedback: ${feedbackUseful ? "Useful" : "Not Useful"}`}
        confirmLabel="Submit Feedback"
        confirmVariant="primary"
        onConfirm={handleFeedbackSubmit}
        busy={busy}
      >
        <p className="small-text muted">
          Your feedback evaluates the clinical relevance of the AI decision support summary for quality governance.
        </p>
        <label className="field" style={{ marginTop: "1rem" }}>
          Optional Comments:
          <input
            value={feedbackReason}
            onChange={(e) => setFeedbackReason(e.target.value)}
            placeholder={feedbackUseful ? "What was helpful? (e.g. Clear duration and red flag check)" : "What was missing or inaccurate?"}
            maxLength={300}
          />
        </label>
      </Dialog>

      {/* Complete Consultation Confirmation Dialog */}
      <Dialog
        open={showCompleteDialog}
        onClose={() => setShowCompleteDialog(false)}
        title="Confirm Complete Consultation"
        confirmLabel="Yes, Save & Finalize Visit"
        confirmVariant="primary"
        onConfirm={handleCompleteConsultation}
        busy={busy}
      >
        <p>Are you ready to finalize this encounter?</p>
        <div className="card" style={{ background: "var(--surface-muted)", margin: "0.5rem 0" }}>
          <div><strong>Diagnosis:</strong> {dx.text}</div>
          {dx.code && <div><strong>ICD-10:</strong> {dx.code}</div>}
          <div><strong>Prescriptions:</strong> {rx.filter((r) => r.drug.trim()).length} medications prescribed</div>
          {dx.follow && <div><strong>Follow-up:</strong> {dx.follow}</div>}
        </div>
        <p className="small-text muted">
          Once finalized, the encounter record will be stored in the electronic health record and made accessible to the patient.
        </p>
      </Dialog>
    </div>
  );
}
