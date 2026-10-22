import { useEffect, useState, type FormEvent } from "react";
import { api, post } from "../shared/api";
import { useAuth } from "../shared/auth";
import { ErrorBox } from "../shared/ui";
import IntakeWizard, { type SessionView } from "../patient/IntakeWizard";

export default function WalkIn() {
  const { me } = useAuth();
  const [assignedDoc, setAssignedDoc] = useState<{ id: number; name: string; specialty: string; room: string } | null>(null);
  const [f, setF] = useState({ full_name: "", age: "", language: "en" });
  const [created, setCreated] = useState<{ entry: { id: number; token_label: string } } | null>(null);
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState<unknown>(null);

  useEffect(() => {
    api<{ assigned_doctor?: { id: number; name: string; specialty: string; room: string } }>("/queue")
      .then((res) => {
        if (res.assigned_doctor) setAssignedDoc(res.assigned_doctor);
      })
      .catch((ex) => setErr(ex));
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      setCreated(await post("/queue/walk-in", {
        full_name: f.full_name,
        age: Number(f.age),
        language: f.language,
      }));
    } catch (ex) {
      setErr(ex);
    }
  };

  const isUnassigned = err ? String(err).includes("No doctor assigned") : false;
  if (isUnassigned) {
    return (
      <div className="panel" style={{ marginTop: "1rem" }}>
        <h1>Register Walk-in</h1>
        <div className="card warn">
          <h2>No Doctor Assigned</h2>
          <p>No doctor assigned. Please contact the administrator.</p>
        </div>
      </div>
    );
  }

  if (result) {
    return (
      <div className={`card ${result.decision.priority === "emergency" ? "red" : result.decision.flag_for_nurse ? "amber" : "ok"}`}>
        <h2>Assisted intake saved · token {created?.entry.token_label}</h2>
        <p>Priority: <strong>{result.decision.priority}</strong> ({result.decision.decided_by === "rule" ? "fixed safety rule" : "AI-assisted"})</p>
        <p>{result.decision.priority_rationale}</p>
        {result.decision.flag_for_nurse && <p>Flagged: appears under “Needs attention”.</p>}
        <button className="btn" onClick={() => { setCreated(null); setResult(null); setF({ full_name: "", age: "", language: "en" }); }}>Register another walk-in</button>
      </div>
    );
  }

  return (
    <div>
      <h1>Walk-in Registration</h1>
      {assignedDoc && (
        <p className="muted" style={{ marginTop: "-0.5rem", marginBottom: "1rem" }}>
          Registering patient for <strong>{assignedDoc.name}</strong> ({assignedDoc.specialty}, {assignedDoc.room})
        </p>
      )}
      <ErrorBox error={err} />
      {!created ? (
        <form className="card" onSubmit={submit}>
          <p className="muted small-text">No phone number or ID is collected.</p>
          <label className="field">Full name<input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} required /></label>
          <label className="field">Age<input type="number" min={0} max={125} value={f.age} onChange={(e) => setF({ ...f, age: e.target.value })} required /></label>
          <label className="field">Language<select value={f.language} onChange={(e) => setF({ ...f, language: e.target.value })}><option value="en">English</option><option value="ta">Tamil</option></select></label>
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
