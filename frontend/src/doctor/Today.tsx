import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, post } from "../shared/api";
import { ErrorBox, Loading } from "../shared/ui";
import { EntryHeader, PriorityChip } from "../nurse/bits";
import type { QEntry } from "../nurse/types";

type TodayResp = {
  doctor: { name: string; specialty: string; hospital: string; room?: string };
  assigned_nurse?: { id: number; name: string } | null;
  date: string; session: string; with_doctor: QEntry | null; next: QEntry | null;
  present: QEntry[]; not_arrived_count: number; done_count: number; order_note: string;
};

export default function Today() {
  const [d, setD] = useState<TodayResp | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const nav = useNavigate();
  const load = useCallback(() => api<TodayResp>("/doctor/today").then(setD).catch(setErr), []);
  useEffect(() => { load(); const h = setInterval(load, 8000); return () => clearInterval(h); }, [load]);
  const callIn = async (e: QEntry) => {
    try { await post(`/doctor/start/${e.id}`); nav(`/staff/doctor/patient/${e.patient_id}?appointment=${e.appointment_id}`); } catch (ex) { setErr(ex); }
  };
  if (!d) return err ? <ErrorBox error={err} onRetry={load} /> : <Loading />;
  return (
    <div>
      <div className="spread" style={{ marginBottom: "1rem" }}>
        <div>
          <h1 style={{ marginBottom: "0.25rem" }}>
            {d.doctor.name} · {d.doctor.specialty} · {d.doctor.room ?? "OPD Room"} · {d.date}
          </h1>
          <div className="small-text muted">
            {d.doctor.hospital} · Assigned Nurse: <strong>{d.assigned_nurse?.name ?? "None assigned"}</strong>
          </div>
        </div>
      </div>
      <ErrorBox error={err} />
      <div className="staff-grid">
        <div>
          {d.with_doctor && (
            <div className="card ok">
              <h2>With you now</h2>
              <EntryHeader e={d.with_doctor} />
              <Link className="btn" to={`/staff/doctor/patient/${d.with_doctor.patient_id}?appointment=${d.with_doctor.appointment_id}`}>Open workspace</Link>
            </div>
          )}
          {d.next && !d.with_doctor && (
            <div className="card">
              <h2>Next patient</h2>
              <EntryHeader e={d.next} />
              <div>{d.next.chief_complaint}</div>
              <PriorityChip e={d.next} />
              <div className="row" style={{ marginTop: 8 }}><button className="btn" onClick={() => callIn(d.next!)}>Call in</button></div>
            </div>
          )}
          <h2>Present patients ({d.present.length})</h2>
          <p className="muted small-text">{d.order_note}</p>
          {d.present.map((e) => (
            <div key={e.id} className={`entry ${e.flagged ? "alert-amber" : ""}`}>
              <EntryHeader e={e} />
              <div>{e.chief_complaint ?? "—"}</div>
              <PriorityChip e={e} /> {e.flagged && <span className="pill same-day">flagged</span>}
              <div className="row" style={{ marginTop: 6 }}>
                <Link className="btn small secondary" to={`/staff/doctor/patient/${e.patient_id}?appointment=${e.appointment_id}`}>Open</Link>
                <button className="btn small" disabled={!!d.with_doctor} onClick={() => callIn(e)}>Call in</button>
              </div>
            </div>
          ))}
        </div>
        <div className="panel">
          <h3>Today</h3>
          <p>Booked, not arrived yet: <strong>{d.not_arrived_count}</strong></p>
          <p>Done: <strong>{d.done_count}</strong></p>
        </div>
      </div>
    </div>
  );
}
