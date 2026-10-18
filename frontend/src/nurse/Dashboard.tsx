import { useCallback, useEffect, useState } from "react";
import { api, post } from "../shared/api";
import { useAuth } from "../shared/auth";
import { ErrorBox, Loading } from "../shared/ui";
import { EntryHeader, PriorityChip, promptReason } from "./bits";
import EntryDrawer from "./EntryDrawer";
import type { DoctorBlock, QEntry } from "./types";

type QueueResp = { date: string; session: string; doctors: DoctorBlock[] };

export default function Dashboard() {
  const { me } = useAuth();
  const [doctors, setDoctors] = useState<{ id: number; name: string; specialty: string }[]>([]);
  const [doctorId, setDoctorId] = useState<string>("");
  const [session, setSession] = useState<string>("");
  const [dept, setDept] = useState<string>("");
  const [data, setData] = useState<QueueResp | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [dragId, setDragId] = useState<number | null>(null);

  useEffect(() => { api("/queue/doctors").then(setDoctors).catch(setErr); }, []);
  const load = useCallback(() => {
    const qs = new URLSearchParams();
    if (doctorId) qs.set("doctor_id", doctorId);
    if (session) qs.set("session", session);
    return api<QueueResp>(`/queue?${qs}`).then((d) => { setData(d); setErr(null); }).catch(setErr);
  }, [doctorId, session]);
  useEffect(() => {
    load();
    const h = setInterval(load, 7000); // polling; no websockets needed
    return () => clearInterval(h);
  }, [load]);

  const act = async (e: QEntry, action: string, extra: Record<string, unknown> = {}) => {
    try { await post("/queue/action", { entry_id: e.id, action, ...extra }); await load(); } catch (ex) { setErr(ex); }
  };
  const changePriority = async (e: QEntry) => {
    const p = window.prompt("New priority: emergency, same-day or routine", e.priority ?? "same-day");
    if (!p) return;
    const reason = promptReason("change the priority");
    if (!reason) return;
    act(e, "change_priority", { priority: p.trim(), reason });
  };
  const setMode = async (b: DoctorBlock, mode: "token" | "nurse") => {
    try { await post("/queue/order", { doctor_id: b.doctor.id, session: data!.session, mode }); await load(); } catch (ex) { setErr(ex); }
  };
  const drop = async (b: DoctorBlock, targetId: number) => {
    if (dragId == null || dragId === targetId) return;
    const ids = b.present_waiting.filter((x) => !x.fast_tracked).map((x) => x.id).filter((i) => i !== dragId);
    ids.splice(ids.indexOf(targetId), 0, dragId);
    try { await post("/queue/order", { doctor_id: b.doctor.id, session: data!.session, mode: "nurse", ordered_entry_ids: ids }); await load(); } catch (ex) { setErr(ex); }
    setDragId(null);
  };

  const blocks = (data?.doctors ?? []).filter((b) => !dept || b.doctor.specialty === dept);
  return (
    <div>
      <div className="spread">
        <h1>{me?.hospital_name} · {data?.date} · {data?.session}</h1>
        <div className="row">
          <select aria-label="Doctor" value={doctorId} onChange={(e) => setDoctorId(e.target.value)}>
            <option value="">All doctors</option>
            {doctors.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.specialty})</option>)}
          </select>
          <select aria-label="Session" value={session} onChange={(e) => setSession(e.target.value)}>
            <option value="">Current session</option><option value="morning">Morning</option><option value="afternoon">Afternoon</option>
          </select>
          <select aria-label="Department" value={dept} onChange={(e) => setDept(e.target.value)}>
            <option value="">All departments</option>
            {Array.from(new Set(doctors.map((d) => d.specialty))).map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
      </div>
      <ErrorBox error={err} onRetry={load} />
      {!data ? <Loading /> : blocks.length === 0 ? <p className="muted">No patients for this filter today.</p> : (
        <>
          <section className="panel" aria-label="Needs attention">
            <h2>🚩 Needs attention</h2>
            {blocks.flatMap((b) => b.needs_attention).length === 0 && <p className="muted">No flagged patients present.</p>}
            {blocks.flatMap((b) => b.needs_attention.map((e) => ({ e, b }))).sort((x, y) => Number(y.e.priority === "emergency") - Number(x.e.priority === "emergency")).map(({ e, b }) => (
              <div key={e.id} className={`entry alert-${e.alert_state}`} data-testid="attention">
                <EntryHeader e={e} />
                <div className="small-text muted">{b.doctor.name}</div>
                <div><strong>{e.chief_complaint ?? "—"}</strong></div>
                {e.red_flags.length > 0 && <div className="small-text">Red flags: {e.red_flags.join(", ")}</div>}
                <PriorityChip e={e} />
                {e.flag_source === "nurse" && <span className="pill nurse">flagged by nurse</span>}
                {e.flag_reason && <div className="small-text">Flag: {e.flag_reason}</div>}
                {e.checkin_change && e.checkin_change !== "none" && <div className="small-text">At check-in: {e.checkin_change.replace("_", " ")}</div>}
                <div className="row" style={{ marginTop: 6 }}>
                  {!e.acknowledged && <button className="btn small" onClick={() => post(`/queue/${e.id}/ack`).then(load).catch(setErr)}>Acknowledge</button>}
                  <button className="btn small danger" onClick={() => act(e, "send_to_er", { reason: promptReason("send to ER") ?? undefined })}>Send to ER</button>
                  {!e.fast_tracked ? <button className="btn small warn" onClick={() => act(e, "fast_track")}>Fast-track</button>
                    : <button className="btn small secondary" onClick={() => act(e, "return_to_queue")}>Return to queue</button>}
                  <button className="btn small secondary" onClick={() => changePriority(e)}>Change priority</button>
                  <button className="btn small ghost" onClick={() => setOpen(e.id)}>Open</button>
                </div>
              </div>
            ))}
          </section>
          {blocks.map((b) => (
            <section className="panel" key={b.doctor.id} style={{ marginTop: "1rem" }}>
              <div className="spread">
                <h2>{b.doctor.name} · {b.doctor.specialty}</h2>
                <div className="row small-text">
                  <span>Now serving: <strong>{b.now_serving ?? "—"}</strong></span>
                  <span>Next: <strong>{b.next?.token_label ?? "—"}</strong></span>
                  <span>Done {b.done_count}/{b.total}</span>
                </div>
              </div>
              <div className="staff-grid">
                <div>
                  <div className="spread">
                    <h3>Present and waiting ({b.present_waiting.length})</h3>
                    <div className="row" role="group" aria-label="Order mode">
                      <button className={`btn small ${b.mode === "token" ? "" : "secondary"}`} onClick={() => setMode(b, "token")}>Token order</button>
                      <button className={`btn small ${b.mode === "nurse" ? "" : "secondary"}`} onClick={() => setMode(b, "nurse")}>My order</button>
                    </div>
                  </div>
                  {b.with_doctor && (
                    <div className="entry" style={{ background: "#e7f5ef" }}>
                      <EntryHeader e={b.with_doctor} /> <span className="pill">with doctor</span>
                      <button className="btn small" onClick={() => act(b.with_doctor!, "mark_done")}>Mark done</button>
                    </div>
                  )}
                  {b.present_waiting.map((e, i) => (
                    <div key={e.id} className={`entry ${dragId === e.id ? "dragging" : ""}`} draggable={b.mode === "nurse" && !e.fast_tracked}
                      onDragStart={() => setDragId(e.id)} onDragOver={(ev) => ev.preventDefault()} onDrop={() => drop(b, e.id)}>
                      <EntryHeader e={e} />
                      <div className="small-text">{e.chief_complaint ?? "—"}</div>
                      <PriorityChip e={e} />
                      <div className="row" style={{ marginTop: 6 }}>
                        {b.mode === "nurse" && !e.fast_tracked && (
                          <>
                            <span aria-hidden title="Drag to reorder">☰</span>
                            <button className="btn small ghost" disabled={i === 0} onClick={() => act(e, "move_up")} aria-label="Move up">▲</button>
                            <button className="btn small ghost" onClick={() => act(e, "move_down")} aria-label="Move down">▼</button>
                          </>
                        )}
                        <button className="btn small" disabled={!!b.with_doctor} onClick={() => act(e, "mark_with_doctor")}>With doctor</button>
                        {!e.fast_tracked ? <button className="btn small warn" onClick={() => act(e, "fast_track")}>Fast-track</button>
                          : <button className="btn small secondary" onClick={() => act(e, "return_to_queue")}>Return to queue</button>}
                        <button className="btn small ghost" onClick={() => setOpen(e.id)}>Open</button>
                      </div>
                    </div>
                  ))}
                </div>
                <div>
                  {b.expected_today_flagged.length > 0 && (
                    <>
                      <h3>⚠️ Expected today (flagged)</h3>
                      {b.expected_today_flagged.map((e) => (
                        <div key={e.id} className="entry alert-amber">
                          <EntryHeader e={e} />
                          <div className="small-text">{e.chief_complaint ?? "—"} · {e.presence === "self_reported_arrived" ? "says they are here" : e.presence.replace(/_/g, " ")}</div>
                          <button className="btn small" onClick={() => setOpen(e.id)}>Check in</button>
                        </div>
                      ))}
                    </>
                  )}
                  <h3>Booked, not arrived ({b.still_to_come} still to come)</h3>
                  {b.booked_not_arrived.map((e) => (
                    <div key={e.id} className="entry">
                      <EntryHeader e={e} />
                      <div className="small-text">{e.chief_complaint ?? "—"} · {e.presence === "self_reported_arrived" ? "🙋 tapped “I'm here”" : e.presence.replace(/_/g, " ")}</div>
                      <div className="row">
                        <button className="btn small" onClick={() => setOpen(e.id)}>{e.presence === "self_reported_arrived" ? "Confirm arrival" : "Check in"}</button>
                        <button className="btn small ghost" onClick={() => act(e, "mark_no_show")}>No-show</button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          ))}
        </>
      )}
      {open != null && <EntryDrawer entryId={open} onClose={() => { setOpen(null); load(); }} />}
    </div>
  );
}
