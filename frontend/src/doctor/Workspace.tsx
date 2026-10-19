import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, post } from "../shared/api";
import { Card, ErrorBox, Loading } from "../shared/ui";

type Rx = { drug: string; dose: string; frequency: string; duration: string; instructions: string };
const emptyRx = (): Rx => ({ drug: "", dose: "", frequency: "", duration: "", instructions: "" });

type WS = {
  patient: { id: number; full_name: string; age: string; language: string };
  appointment: { id: number; status: string; token_label: string | null; date: string } | null;
  entry: { priority: string | null; priority_rationale: string | null; decided_by: string | null; audit_notes: string[] } | null;
  summary: { priority: string; priority_rationale: string; decided_by: string | null; audit_notes: string[]; input_confidence: string | null } | null;
  lines: string[]; answers: any; vitals: any;
  history: { own: any[]; shared: any[]; shared_label: string | null; consent: boolean };
};

const NOTE_TEXT: Record<string, string> = {
  injection_suspected: "Injection suspected in patient text (escalated; rules ran on the original text)",
  low_input_confidence: "Low input confidence",
  llm_fallback_used: "AI estimate unavailable or unsure: fail-safe used",
  output_filtered: "AI text was filtered for diagnosis/medication language",
  patient_reported_worse_at_checkin: "Patient reported worse at check-in",
  patient_reported_new_symptom_at_checkin: "Patient reported a new symptom at check-in",
  patient_reported_change: "Patient reported a change since booking",
  recheck_addendum: "Short re-check added",
};

export default function Workspace() {
  const { patientId } = useParams();
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const [ws, setWs] = useState<WS | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [dx, setDx] = useState({ text: "", code: "", notes: "", follow: "" });
  const [rx, setRx] = useState<Rx[]>([emptyRx()]);
  const [busy, setBusy] = useState(false);
  const appt = sp.get("appointment");
  const load = () => api<WS>(`/doctor/patient/${patientId}${appt ? `?appointment_id=${appt}` : ""}`).then(setWs).catch(setErr);
  useEffect(() => { load(); }, [patientId, appt]); // eslint-disable-line react-hooks/exhaustive-deps

  const changePriority = async () => {
    if (!ws?.appointment) return;
    const p = window.prompt("New priority: emergency, same-day or routine");
    if (!p) return;
    const reason = window.prompt("Reason (required):");
    if (!reason?.trim()) return;
    try { await post("/doctor/override", { appointment_id: ws.appointment.id, priority: p.trim(), reason }); load(); } catch (e) { setErr(e); }
  };
  const complete = async (e: FormEvent) => {
    e.preventDefault();
    if (!ws?.appointment) return;
    setBusy(true);
    try {
      await post("/ehr/consultation", {
        appointment_id: ws.appointment.id, diagnosis_text: dx.text, diagnosis_code: dx.code || undefined, clinical_notes: dx.notes,
        prescription: rx.filter((r) => r.drug.trim()), follow_up_date: dx.follow || undefined,
      });
      nav("/staff/doctor");
    } catch (ex) { setErr(ex); } finally { setBusy(false); }
  };
  if (!ws) return err ? <ErrorBox error={err} /> : <Loading />;
  const notes = Array.from(new Set([...(ws.summary?.audit_notes ?? []), ...(ws.entry?.audit_notes ?? [])]));
  const open = ws.appointment && !["completed", "cancelled", "no_show"].includes(ws.appointment.status);
  const setR = (i: number, k: keyof Rx, v: string) => setRx(rx.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  return (
    <div>
      <h1>{ws.patient.full_name} · age {ws.patient.age} {ws.appointment?.token_label ? `· ${ws.appointment.token_label}` : ""}</h1>
      <ErrorBox error={err} />
      <div className="staff-grid">
        <div>
          <Card>
            <div className="spread">
              <h2>1. Triage summary</h2>
              {ws.appointment && <button className="btn small secondary" onClick={changePriority}>Change priority</button>}
            </div>
            {ws.lines.length ? <ul className="summary-lines">{ws.lines.map((l) => <li key={l}>{l}</li>)}</ul> : <p className="muted">No intake for this visit.</p>}
            {ws.summary && <p className="small-text">Decided by: <strong>{ws.summary.decided_by === "rule" ? "fixed safety rule" : ws.summary.decided_by === "human" ? "staff" : ws.summary.decided_by === "fallback" ? "fail-safe (AI unavailable)" : "AI-assisted"}</strong> · input confidence: {ws.summary.input_confidence}</p>}
            {notes.length > 0 && <div className="notice small-text"><strong>Please note:</strong><ul>{notes.map((n) => <li key={n}>{NOTE_TEXT[n] ?? n.replace(/_/g, " ")}</li>)}</ul></div>}
            {ws.vitals && <p className="small-text">Vitals: BP {ws.vitals.bp_sys ?? "-"}/{ws.vitals.bp_dia ?? "-"}, T {ws.vitals.temp_c ?? "-"}°C, SpO2 {ws.vitals.spo2 ?? "-"}%, pulse {ws.vitals.pulse ?? "-"}</p>}
            {ws.answers && <details><summary>Patient's own words</summary><p><em>“{ws.answers.your_words}”</em></p></details>}
          </Card>
          {open ? (
            <form className="card" onSubmit={complete}>
              <h2>3. Consultation</h2>
              <p className="muted small-text">Typed by you only. Nothing here is suggested or filled in by AI.</p>
              <label className="field">Diagnosis (your words)<input value={dx.text} onChange={(e) => setDx({ ...dx, text: e.target.value })} required maxLength={500} autoComplete="off" /></label>
              <label className="field">Code (optional)<input value={dx.code} onChange={(e) => setDx({ ...dx, code: e.target.value })} maxLength={20} autoComplete="off" /></label>
              <label className="field">Clinical notes<textarea value={dx.notes} onChange={(e) => setDx({ ...dx, notes: e.target.value })} maxLength={5000} /></label>
              <h3>Prescription</h3>
              {rx.map((r, i) => (
                <div className="rx-row" key={i}>
                  <label>Drug<input value={r.drug} onChange={(e) => setR(i, "drug", e.target.value)} autoComplete="off" /></label>
                  <label>Dose<input value={r.dose} onChange={(e) => setR(i, "dose", e.target.value)} autoComplete="off" /></label>
                  <label>Frequency<input value={r.frequency} onChange={(e) => setR(i, "frequency", e.target.value)} autoComplete="off" /></label>
                  <label>Duration<input value={r.duration} onChange={(e) => setR(i, "duration", e.target.value)} autoComplete="off" /></label>
                  <label>Instructions<input value={r.instructions} onChange={(e) => setR(i, "instructions", e.target.value)} autoComplete="off" /></label>
                  <button type="button" className="btn small ghost" onClick={() => setRx(rx.filter((_, j) => j !== i))} aria-label="Remove row">✕</button>
                </div>
              ))}
              <button type="button" className="btn small secondary" onClick={() => setRx([...rx, emptyRx()])}>+ Add medicine</button>
              <label className="field">Follow-up date<input type="date" value={dx.follow} onChange={(e) => setDx({ ...dx, follow: e.target.value })} /></label>
              <button className="btn block" disabled={busy}>4. Complete consultation</button>
            </form>
          ) : <p className="muted">This visit is {ws.appointment?.status ?? "not active"}.</p>}
        </div>
        <div className="panel">
          <h2>2. History</h2>
          <h3>Your encounters with this patient</h3>
          {ws.history.own.length === 0 && <p className="muted">None.</p>}
          {ws.history.own.map((e) => (
            <div className="entry" key={e.id}>
              <strong>{e.date}</strong> · {e.diagnosis_text} {e.diagnosis_code ? `(${e.diagnosis_code})` : ""}
              {e.clinical_notes && <div className="small-text">Notes: {e.clinical_notes}</div>}
              {e.prescriptions.map((p: Rx, i: number) => <div className="small-text" key={i}>℞ {p.drug} {p.dose} {p.frequency} {p.duration}</div>)}
            </div>
          ))}
          <h3>Other doctors</h3>
          {!ws.history.consent ? <p className="muted">Patient has not consented to sharing. Nothing from other doctors is shown.</p> : (
            <>
              {ws.history.shared_label && <p className="pill">{ws.history.shared_label}</p>}
              {ws.history.shared.length === 0 && <p className="muted">None.</p>}
              {ws.history.shared.map((e) => <div className="entry" key={e.id}><strong>{e.date}</strong> · {e.specialty} · {e.hospital_name}<div>{e.diagnosis_text}</div></div>)}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
