import { useState } from "react";
import type { QEntry } from "./types";

export function PriorityChip({ e }: { e: QEntry }) {
  const [open, setOpen] = useState(false);
  if (!e.priority) return <span className="pill">no intake yet</span>;
  return (
    <span>
      <button className={`pill ${e.priority}`} onClick={() => setOpen((o) => !o)} aria-expanded={open} title="Show rationale">
        {e.priority} {open ? "▲" : "▼"}
      </button>{" "}
      <span className={`pill ${e.rule_based ? "rule" : "ai"}`}>{e.rule_based ? "fixed safety rule" : e.decided_by === "human" ? "changed by staff" : "AI-assisted"}</span>
      {open && <div className="small-text" style={{ marginTop: 4 }}>{e.priority_rationale}</div>}
    </span>
  );
}

export function waitText(s: number | null) {
  if (s == null) return "";
  const m = Math.floor(s / 60);
  return m < 1 ? "just arrived" : `waiting ${m} min`;
}

export function EntryHeader({ e }: { e: QEntry }) {
  return (
    <div className="spread">
      <div>
        <span className="tok">{e.token_label ?? "—"}</span>
        <strong>{e.patient_name}</strong>
        {e.appointment_type === "walk_in" && <span className="pill"> walk-in</span>}
        {e.late_arrival && <span className="pill"> late arrival</span>}
        {e.fast_tracked && <span className="pill same-day"> fast-tracked</span>}
      </div>
      <span className="muted small-text">{waitText(e.waiting_seconds)}</span>
    </div>
  );
}

