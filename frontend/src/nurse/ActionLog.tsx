import { useEffect, useState } from "react";
import { api } from "../shared/api";
import { ErrorBox, Loading } from "../shared/ui";

type Row = { id: number; ts: string; actor_name: string; actor_role: string; action: string; patient_id: number | null; original_value: string | null; new_value: string | null; reason: string | null };

export default function ActionLog() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const load = () => api<Row[]>("/queue/action-log").then(setRows).catch(setErr);
  useEffect(() => { load(); const h = setInterval(load, 10000); return () => clearInterval(h); }, []);
  if (err) return <ErrorBox error={err} onRetry={load} />;
  if (!rows) return <Loading />;
  return (
    <div className="panel">
      <h1>Action log</h1>
      <table className="log">
        <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Patient</th><th>Original</th><th>New</th><th>Reason</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{new Date(r.ts).toLocaleTimeString()}</td><td>{r.actor_name} ({r.actor_role})</td><td>{r.action.replace(/_/g, " ")}</td>
              <td>{r.patient_id ?? ""}</td><td>{r.original_value ?? ""}</td><td>{r.new_value ?? ""}</td><td>{r.reason ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
