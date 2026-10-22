import { useEffect, useState, type FormEvent } from "react";
import { api, post } from "../shared/api";
import { ErrorBox, Loading, Dialog, Button, Field } from "../shared/ui";
import IntakeWizard, { type SessionView } from "../patient/IntakeWizard";
import { EntryHeader, PriorityChip } from "./bits";
import type { QEntry } from "./types";

type Detail = { entry: QEntry; lines: string[]; answers: any; vitals: any; summary: any };
const SCREEN = [
  ["chest_pain", "Chest pain", "chest pain"], ["trouble_breathing", "Trouble breathing", "trouble breathing"],
  ["fainting", "Fainting or blackout", "fainted"], ["severe_bleeding", "Severe bleeding", "severe bleeding"],
  ["sudden_weakness", "Sudden weakness or numbness", "sudden weakness"], ["confusion", "Confusion", "confused"], ["seizure", "Seizure", "having a seizure now"],
];

export function CheckInPanel({ entry, onDone }: { entry: QEntry; onDone: (res: any) => void }) {
  const [note, setNote] = useState("");
  const [screenOpen, setScreenOpen] = useState(false);
  const [chips, setChips] = useState<string[]>([]);
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const send = async (o: string) => {
    setBusy(true);
    const screenText = chips.map((c) => SCREEN.find((s) => s[0] === c)![2]).join(", ");
    const finalOutcome = chips.length && o !== "worse" ? "new_symptom" : o;
    const fullNote = [note.trim(), screenText ? `Quick safety screen: ${screenText}` : ""].filter(Boolean).join(". ");
    try { onDone(await post(`/queue/${entry.id}/check-in`, { outcome: finalOutcome, note: fullNote || undefined })); } catch (e) { setErr(e); } finally { setBusy(false); }
  };
  return (
    <div className="card">
      <h3>{entry.presence === "self_reported_arrived" ? "Confirm arrival" : "Check in"} · ask in your own words: “Since you booked, is anything worse or new?”</h3>
      {entry.checkin_change && <p className="small-text">Patient's own answer in the app: <strong>{entry.checkin_change.replace("_", " ")}</strong></p>}
      <label className="field">Note (optional, what the patient says)<textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} /></label>
      <div className="row">
        <button className="btn" disabled={busy} onClick={() => send("none")}>No change</button>
        <button className="btn secondary" disabled={busy} onClick={() => send("better")}>Better</button>
        <button className="btn warn" disabled={busy} onClick={() => send("worse")}>Worse</button>
        <button className="btn warn" disabled={busy} onClick={() => send("new_symptom")}>New symptom</button>
      </div>
      <button className="btn small ghost" style={{ marginTop: 8 }} onClick={() => setScreenOpen((o) => !o)}>Quick safety screen (optional)</button>
      {screenOpen && (
        <div className="chips">
          {SCREEN.map(([k, label]) => (
            <button key={k} className={`chip ${chips.includes(k) ? "on" : ""}`} onClick={() => setChips((c) => (c.includes(k) ? c.filter((x) => x !== k) : [...c, k]))}>{label}</button>
          ))}
        </div>
      )}
      <ErrorBox error={err} />
    </div>
  );
}

export function Recheck({ entryId, change, onDone }: { entryId: number; change: string; onDone: (r: any) => void }) {
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState<unknown>(null);
  if (result) {
    return (
      <div className={`card ${result.priority_raised ? "red" : "ok"}`}>
        <strong>Re-check done.</strong> {result.priority_raised ? `Priority raised: ${result.raise_reasons.join("; ")}.` : "Priority unchanged (re-checks can only raise it)."}
        <button className="btn small" onClick={() => onDone(result)}>Close</button>
      </div>
    );
  }
  return (
    <div className="card">
      <h3>Short re-check (assisted)</h3>
      <ErrorBox error={err} />
      <IntakeWizard staff confirm={false}
        start={() => post<SessionView>(`/queue/${entryId}/recheck/start?change=${change === "new_symptom" ? "new_symptom" : "worse"}`)}
        onFinished={(sid) => post("/pipeline/submit", { intake_session_id: sid }).then(setResult).catch(setErr)} />
    </div>
  );
}

function Vitals({ entryId, onSaved }: { entryId: number; onSaved: () => void }) {
  const [v, setV] = useState({ bp_sys: "", bp_dia: "", temp_c: "", spo2: "", pulse: "" });
  const [msg, setMsg] = useState<{ text: string; raised: boolean } | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const body: Record<string, number> = {};
    for (const [k, val] of Object.entries(v)) if (val !== "") body[k] = Number(val);
    try {
      const r = await post("/queue/vitals", { entry_id: entryId, ...body });
      setMsg({ text: r.message, raised: r.priority_raised });
      onSaved();
    } catch (ex) { setErr(ex); }
  };
  const f = (k: keyof typeof v, label: string, step = "1") => (
    <label className="field" style={{ flex: 1, minWidth: 110 }}>{label}<input type="number" step={step} value={v[k]} onChange={(e) => setV({ ...v, [k]: e.target.value })} /></label>
  );
  return (
    <form className="card" onSubmit={submit}>
      <h3>Vitals</h3>
      <div className="row">{f("bp_sys", "BP systolic")}{f("bp_dia", "BP diastolic")}{f("temp_c", "Temp °C", "0.1")}{f("spo2", "SpO2 %")}{f("pulse", "Pulse")}</div>
      <button className="btn">Save vitals</button>
      {msg && <p className={msg.raised ? "error" : "notice"}>{msg.text}</p>}
      <ErrorBox error={err} />
    </form>
  );
}

export default function EntryDrawer({ entryId, onClose }: { entryId: number; onClose: () => void }) {
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [recheck, setRecheck] = useState<string | null>(null);
  const load = () => api<Detail>(`/queue/entry/${entryId}`).then(setD).catch(setErr);
  useEffect(() => { load(); }, [entryId]); // eslint-disable-line react-hooks/exhaustive-deps
  const [flagModal, setFlagModal] = useState<{ flagged: boolean; reason: string } | null>(null);
  const [flagSubmitting, setFlagSubmitting] = useState(false);

  const confirmFlag = async () => {
    if (!flagModal || !flagModal.reason.trim()) return;
    setFlagSubmitting(true);
    try {
      await post("/queue/flag", {
        entry_id: entryId,
        flagged: flagModal.flagged,
        reason: flagModal.reason.trim(),
      });
      setFlagModal(null);
      load();
    } catch (e) {
      setErr(e);
    } finally {
      setFlagSubmitting(false);
    }
  };
  return (
    <aside className="drawer" role="dialog" aria-label="Patient details">
      <div className="spread"><h2>Patient</h2><button className="btn small ghost" onClick={onClose}>Close</button></div>
      <ErrorBox error={err} />
      {!d ? <Loading /> : (
        <>
          <EntryHeader e={d.entry} />
          <PriorityChip e={d.entry} />
          {d.entry.audit_notes.length > 0 && (
            <div className="notice small-text" style={{ margin: "0.5rem 0" }}>
              <strong>Clinical notes:</strong>
              <ul style={{ margin: "0.25rem 0 0 0", paddingLeft: "1.2rem" }}>
                {d.entry.audit_notes.map((n) => (
                  <li key={n}>
                    {n === "ai_unavailable_escalated"
                      ? "AI unavailable: escalated for safety"
                      : n === "llm_fallback_used"
                      ? "AI estimate unavailable or unsure: fail-safe used"
                      : n === "fallback_mild_allowlist"
                      ? "Deterministic fallback: mild allowlist (routine)"
                      : n === "injection_suspected"
                      ? "Instruction-like text detected (escalated; safety rules ran on original text)"
                      : n.replace(/_/g, " ")}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="card">
            <h3>Triage summary</h3>
            {d.lines.length ? <ul className="summary-lines">{d.lines.map((l) => <li key={l}>{l}</li>)}</ul> : <p className="muted">No intake yet. Run assisted intake from the Walk-in tab.</p>}
            {d.answers && (
              <details>
                <summary>Patient's answers {d.answers.assisted ? "(assisted)" : ""}</summary>
                <p><em>“{d.answers.your_words}”</em></p>
                <ul className="small-text">{Object.entries(d.answers.follow_up_answers ?? {}).map(([k, v]) => <li key={k}>{k}: {String(v)}</li>)}</ul>
                <p className="small-text">Safety screen: {(d.answers.safety_screen ?? []).join(", ") || "—"}</p>
                {(d.answers.addenda ?? []).map((a: any, i: number) => <p className="small-text" key={i}>Change ({a.change}, {a.source}): “{a.text}”</p>)}
              </details>
            )}
            <p className="muted small-text">Nurses see the triage summary only, never diagnosis history or prescriptions.</p>
          </div>
          {d.entry.presence !== "present" && d.entry.status === "waiting" && (
            <CheckInPanel entry={d.entry} onDone={(r) => { load(); if (r.recheck_recommended) setRecheck(d.entry.checkin_change ?? "worse"); }} />
          )}
          {d.entry.presence === "present" && !recheck && (
            <div className="row">
              <button className="btn secondary small" onClick={() => setRecheck("worse")}>Start short re-check</button>
            </div>
          )}
          {recheck && <Recheck entryId={entryId} change={recheck} onDone={() => { setRecheck(null); load(); }} />}
          {d.entry.presence === "present" && <Vitals entryId={entryId} onSaved={load} />}
          <div className="row">
            {d.entry.flagged ? (
              <button
                className="btn small secondary"
                onClick={() => setFlagModal({ flagged: false, reason: "" })}
              >
                Unflag
              </button>
            ) : (
              <button
                className="btn small warn"
                onClick={() => setFlagModal({ flagged: true, reason: "" })}
              >
                Flag for attention
              </button>
            )}
          </div>

          <Dialog
            open={!!flagModal}
            onClose={() => !flagSubmitting && setFlagModal(null)}
            title={flagModal?.flagged ? "Flag Patient for Attention" : "Remove Attention Flag"}
            footer={
              <>
                <Button
                  variant="ghost"
                  onClick={() => setFlagModal(null)}
                  disabled={flagSubmitting}
                >
                  Cancel
                </Button>
                <Button
                  variant={flagModal?.flagged ? "warn" : "primary"}
                  onClick={confirmFlag}
                  disabled={flagSubmitting || !flagModal?.reason.trim()}
                  loading={flagSubmitting}
                >
                  {flagModal?.flagged ? "Confirm Flag" : "Confirm Unflag"}
                </Button>
              </>
            }
          >
            <p className="small-text muted">
              All flag status changes are logged with actor, timestamp, and clinical rationale.
            </p>
            <Field label="Clinical Reason" required>
              <textarea
                rows={3}
                placeholder="State clinical observation or reason for flag change..."
                value={flagModal?.reason ?? ""}
                onChange={(e) =>
                  setFlagModal((prev) => (prev ? { ...prev, reason: e.target.value } : null))
                }
                autoFocus
              />
            </Field>
          </Dialog>
        </>
      )}
    </aside>
  );
}
