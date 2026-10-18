import { useEffect, useState, type FormEvent } from "react";
import { api, post } from "../shared/api";
import { ErrorBox } from "../shared/ui";
import IntakeWizard, { type SessionView } from "../patient/IntakeWizard";

export default function WalkIn() {
  const [doctors, setDoctors] = useState<{ id: number; name: string; specialty: string }[]>([]);
  const [f, setF] = useState({ full_name: "", age: "", language: "en", doctor_id: "" });
  const [created, setCreated] = useState<{ entry: { id: number; token_label: string } } | null>(null);
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => { api("/queue/doctors").then(setDoctors).catch(setErr); }, []);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try { setCreated(await post("/queue/walk-in", { full_name: f.full_name, age: Number(f.age), language: f.language, doctor_id: Number(f.doctor_id) })); } catch (ex) { setErr(ex); }
  };
  if (result) {
    return (
      <div className={`card ${result.decision.priority === "emergency" ? "red" : result.decision.flag_for_nurse ? "amber" : "ok"}`}>
        <h2>Assisted intake saved · token {created?.entry.token_label}</h2>
        <p>Priority: <strong>{result.decision.priority}</strong> ({result.decision.decided_by === "rule" ? "fixed safety rule" : "AI-assisted"})</p>
        <p>{result.decision.priority_rationale}</p>
        {result.decision.flag_for_nurse && <p>Flagged: appears under “Needs attention”.</p>}
        <button className="btn" onClick={() => { setCreated(null); setResult(null); setF({ full_name: "", age: "", language: "en", doctor_id: "" }); }}>Register another walk-in</button>
      </div>
    );
  }
  return (
    <div>
      <h1>Walk-in</h1>
      <ErrorBox error={err} />
      {!created ? (
        <form className="card" onSubmit={submit}>
          <p className="muted small-text">No phone number or ID is collected.</p>
          <label className="field">Full name<input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} required /></label>
          <label className="field">Age<input type="number" min={0} max={125} value={f.age} onChange={(e) => setF({ ...f, age: e.target.value })} required /></label>
          <label className="field">Language<select value={f.language} onChange={(e) => setF({ ...f, language: e.target.value })}><option value="en">English</option><option value="ta">Tamil</option></select></label>
          <label className="field">Doctor<select value={f.doctor_id} onChange={(e) => setF({ ...f, doctor_id: e.target.value })} required>
            <option value="">Choose…</option>{doctors.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.specialty})</option>)}
          </select></label>
          <button className="btn block">Register and issue W token</button>
        </form>
      ) : (
        <>
          <div className="card ok"><strong>Token {created.entry.token_label}</strong> issued. Now run the assisted intake: type or speak the patient's answers in their own words.</div>
          <IntakeWizard staff confirm={false}
            start={() => post<SessionView>("/queue/assisted-intake/start", { entry_id: created.entry.id })}
            onFinished={(sid) => post("/pipeline/submit", { intake_session_id: sid }).then(setResult).catch(setErr)} />
        </>
      )}
    </div>
  );
}
