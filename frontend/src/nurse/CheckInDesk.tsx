import { useState, type FormEvent } from "react";
import { api } from "../shared/api";
import { ErrorBox } from "../shared/ui";
import { EntryHeader } from "./bits";
import EntryDrawer from "./EntryDrawer";
import type { QEntry } from "./types";

export default function CheckInDesk() {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<QEntry[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [open, setOpen] = useState<number | null>(null);
  const search = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!q.trim()) return;
    try { setRows(await api(`/queue/search?query=${encodeURIComponent(q.trim())}`)); } catch (ex) { setErr(ex); }
  };
  return (
    <div>
      <h1>Check-in desk</h1>
      <form className="row" onSubmit={search}>
        <input type="text" placeholder="Token (e.g. M-07) or name" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search by token or name" style={{ flex: 1 }} />
        <button className="btn">Search</button>
      </form>
      <ErrorBox error={err} />
      {rows?.length === 0 && <p className="muted">No match today.</p>}
      {rows?.map((e) => (
        <div className="entry" key={e.id}>
          <EntryHeader e={e} />
          <div className="small-text">{e.chief_complaint ?? "—"} · {e.presence.replace(/_/g, " ")} · {e.status}</div>
          <button className="btn small" onClick={() => setOpen(e.id)}>{e.presence === "self_reported_arrived" ? "Confirm arrival" : e.presence === "present" ? "Open" : "Check in"}</button>
        </div>
      ))}
      {open != null && <EntryDrawer entryId={open} onClose={() => { setOpen(null); search(); }} />}
    </div>
  );
}
