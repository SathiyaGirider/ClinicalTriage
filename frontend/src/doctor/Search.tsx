import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../shared/api";
import { ErrorBox } from "../shared/ui";

type P = { patient_id: number; full_name: string; encounters: { id: number; date: string; diagnosis_text: string }[] };

export default function Search() {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<P[]>([]);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => {
    const h = setTimeout(() => api<P[]>(`/doctor/patients?query=${encodeURIComponent(q)}`).then(setRows).catch(setErr), 250);
    return () => clearTimeout(h);
  }, [q]);
  return (
    <div>
      <h1>My patients</h1>
      <input type="text" placeholder="Search by name" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search patients" />
      <ErrorBox error={err} />
      {rows.map((p) => (
        <div className="entry" key={p.patient_id}>
          <div className="spread"><strong>{p.full_name}</strong><Link className="btn small secondary" to={`/staff/doctor/patient/${p.patient_id}`}>Open</Link></div>
          {p.encounters.map((e) => <div className="small-text" key={e.id}>{e.date} · {e.diagnosis_text}</div>)}
        </div>
      ))}
    </div>
  );
}
