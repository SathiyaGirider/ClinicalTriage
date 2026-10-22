import { useCallback, useEffect, useState } from "react";
import { api, post } from "../shared/api";
import { useAuth } from "../shared/auth";
import {
  ErrorBox,
  Loading,
  Dialog,
  Button,
  Field,
  Select,
  Banner,
} from "../shared/ui";
import { EntryHeader, PriorityChip } from "./bits";
import EntryDrawer from "./EntryDrawer";
import type { DoctorBlock, QEntry, QueueResp } from "./types";
import { AlertTriangleIcon, FlagIcon } from "../shared/icons";

export default function Dashboard() {
  const { me } = useAuth();
  const [session, setSession] = useState<string>("");
  const [data, setData] = useState<QueueResp | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [dragId, setDragId] = useState<number | null>(null);

  // Modals replacing window.prompt
  const [priorityModal, setPriorityModal] = useState<{
    entry: QEntry;
    priority: string;
    reason: string;
  } | null>(null);
  const [prioritySubmitting, setPrioritySubmitting] = useState(false);

  const [erModal, setErModal] = useState<{
    entry: QEntry;
    reason: string;
  } | null>(null);
  const [erSubmitting, setErSubmitting] = useState(false);

  // Simulated Scan & Share Modal
  const [scanModalOpen, setScanModalOpen] = useState(false);
  const [scanForm, setScanForm] = useState({
    full_name: "",
    age: "",
    gender: "female",
    abha_address: "",
  });
  const [scanSubmitting, setScanSubmitting] = useState(false);
  const [scanResult, setScanResult] = useState<any>(null);

  const load = useCallback(() => {
    const qs = new URLSearchParams();
    if (session) qs.set("session", session);
    return api<QueueResp>(`/queue?${qs}`)
      .then((d) => {
        setData(d);
        setErr(null);
      })
      .catch(setErr);
  }, [session]);

  useEffect(() => {
    load();
    const h = setInterval(load, 7000); // polling
    return () => clearInterval(h);
  }, [load]);

  const act = async (e: QEntry, action: string, extra: Record<string, unknown> = {}) => {
    try {
      await post("/queue/action", { entry_id: e.id, action, ...extra });
      await load();
    } catch (ex) {
      setErr(ex);
    }
  };

  const confirmChangePriority = async () => {
    if (!priorityModal || !priorityModal.reason.trim()) return;
    setPrioritySubmitting(true);
    try {
      await post("/queue/action", {
        entry_id: priorityModal.entry.id,
        action: "change_priority",
        priority: priorityModal.priority,
        reason: priorityModal.reason.trim(),
      });
      setPriorityModal(null);
      await load();
    } catch (ex) {
      setErr(ex);
    } finally {
      setPrioritySubmitting(false);
    }
  };

  const confirmSendToEr = async () => {
    if (!erModal || !erModal.reason.trim()) return;
    setErSubmitting(true);
    try {
      await post("/queue/action", {
        entry_id: erModal.entry.id,
        action: "send_to_er",
        reason: erModal.reason.trim(),
      });
      setErModal(null);
      await load();
    } catch (ex) {
      setErr(ex);
    } finally {
      setErSubmitting(false);
    }
  };

  const submitScanAndShare = async (e: React.FormEvent) => {
    e.preventDefault();
    setScanSubmitting(true);
    setScanResult(null);
    try {
      const res = await post("/abdm/scan-and-share", {
        full_name: scanForm.full_name.trim(),
        age: Number(scanForm.age),
        gender: scanForm.gender,
        abha_address: scanForm.abha_address.trim(),
      });
      setScanResult(res);
      await load();
    } catch (ex) {
      setErr(ex);
    } finally {
      setScanSubmitting(false);
    }
  };

  const fillDemoScan = () => {
    setScanForm({
      full_name: "Anitha Kumar",
      age: "32",
      gender: "female",
      abha_address: "anitha.kumar@abdm",
    });
  };

  const setMode = async (b: DoctorBlock, mode: "token" | "nurse") => {
    try {
      await post("/queue/order", { session: data!.session, mode });
      await load();
    } catch (ex) {
      setErr(ex);
    }
  };

  const drop = async (b: DoctorBlock, targetId: number) => {
    if (dragId == null || dragId === targetId) return;
    const ids = b.present_waiting
      .filter((x) => !x.fast_tracked)
      .map((x) => x.id)
      .filter((i) => i !== dragId);
    ids.splice(ids.indexOf(targetId), 0, dragId);
    try {
      await post("/queue/order", {
        session: data!.session,
        mode: "nurse",
        ordered_entry_ids: ids,
      });
      await load();
    } catch (ex) {
      setErr(ex);
    }
    setDragId(null);
  };

  const b = data?.doctors?.[0] ?? null;
  const isUnassigned =
    !data?.assigned_doctor && (err ? String(err).includes("No doctor assigned") : false);

  if (isUnassigned || (data && !data.assigned_doctor && !b)) {
    return (
      <div className="panel" style={{ marginTop: "1rem" }}>
        <h1>Nurse Dashboard</h1>
        <div className="card warn">
          <h2>No Doctor Assigned</h2>
          <p>No doctor assigned. Please contact the administrator.</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="spread" style={{ alignItems: "flex-start", gap: "1rem" }}>
        <div>
          {b && (
            <h1 style={{ marginBottom: "0.25rem", fontSize: "1.35rem" }}>
              {b.doctor.name} · {b.doctor.specialty} · {b.doctor.room ?? "Room 101"} ·{" "}
              <span style={{ textTransform: "capitalize" }}>{data?.session}</span> session · Now serving:{" "}
              <strong>{b.now_serving ?? "—"}</strong>
            </h1>
          )}
          <div className="small-text muted">
            {me?.hospital_name} · {data?.date}
          </div>
        </div>
        <div className="row" style={{ alignItems: "center", gap: "0.5rem" }}>
          <Button
            variant="secondary"
            size="small"
            onClick={() => {
              setScanResult(null);
              setScanModalOpen(true);
            }}
          >
            Scan &amp; Share (Simulated)
          </Button>
          <select
            aria-label="Session"
            value={session}
            onChange={(e) => setSession(e.target.value)}
            style={{ minWidth: 140 }}
          >
            <option value="">Current session</option>
            <option value="morning">Morning</option>
            <option value="afternoon">Afternoon</option>
          </select>
        </div>
      </div>

      <ErrorBox error={err} onRetry={load} />

      {!data ? (
        <Loading />
      ) : !b ? (
        <div className="card warn">
          <h2>No Doctor Assigned</h2>
          <p>No doctor assigned. Please contact the administrator.</p>
        </div>
      ) : (
        <>
          <section className="panel" aria-label="Needs attention" style={{ marginTop: "1rem" }}>
            <h2 className="row" style={{ alignItems: "center", gap: "0.5rem" }}>
              <FlagIcon width={20} height={20} style={{ color: "var(--status-emergency-solid)" }} />
              <span>Needs attention ({b.needs_attention.length})</span>
            </h2>
            {b.needs_attention.length === 0 && (
              <p className="muted">No flagged patients present.</p>
            )}
            {b.needs_attention.map((e) => (
              <div key={e.id} className={`entry alert-${e.alert_state}`} data-testid="attention">
                <EntryHeader e={e} />
                <div>
                  <strong>{e.chief_complaint ?? "—"}</strong>
                </div>
                {e.red_flags.length > 0 && (
                  <div className="small-text">Red flags: {e.red_flags.join(", ")}</div>
                )}
                <PriorityChip e={e} />
                {e.flag_source === "nurse" && <span className="pill nurse">flagged by nurse</span>}
                {e.flag_reason && <div className="small-text">Flag: {e.flag_reason}</div>}
                {e.checkin_change && e.checkin_change !== "none" && (
                  <div className="small-text">
                    At check-in: {e.checkin_change.replace("_", " ")}
                  </div>
                )}
                <div className="row" style={{ marginTop: 6 }}>
                  {!e.acknowledged && (
                    <button
                      className="btn small"
                      onClick={() => post(`/queue/${e.id}/ack`).then(load).catch(setErr)}
                    >
                      Acknowledge
                    </button>
                  )}
                  <button
                    className="btn small danger"
                    onClick={() => setErModal({ entry: e, reason: "" })}
                  >
                    Send to ER
                  </button>
                  {!e.fast_tracked ? (
                    <button className="btn small warn" onClick={() => act(e, "fast_track")}>
                      Fast-track
                    </button>
                  ) : (
                    <button
                      className="btn small secondary"
                      onClick={() => act(e, "return_to_queue")}
                    >
                      Return to queue
                    </button>
                  )}
                  <button
                    className="btn small secondary"
                    onClick={() =>
                      setPriorityModal({
                        entry: e,
                        priority: e.priority ?? "same-day",
                        reason: "",
                      })
                    }
                  >
                    Change priority
                  </button>
                  <button className="btn small ghost" onClick={() => setOpen(e.id)}>
                    Open
                  </button>
                </div>
              </div>
            ))}
          </section>

          <section className="panel" key={b.doctor.id} style={{ marginTop: "1rem" }}>
            <div className="spread">
              <h2>Patient Queue</h2>
              <div className="row small-text">
                <span>
                  Next: <strong>{b.next?.token_label ?? "—"}</strong>
                </span>
                <span>
                  Done {b.done_count}/{b.total}
                </span>
              </div>
            </div>
            <div className="staff-grid">
              <div>
                <div className="spread">
                  <h3>Present and waiting ({b.present_waiting.length})</h3>
                  <div className="row" role="group" aria-label="Order mode">
                    <button
                      className={`btn small ${b.mode === "token" ? "" : "secondary"}`}
                      onClick={() => setMode(b, "token")}
                    >
                      Token order
                    </button>
                    <button
                      className={`btn small ${b.mode === "nurse" ? "" : "secondary"}`}
                      onClick={() => setMode(b, "nurse")}
                    >
                      My order
                    </button>
                  </div>
                </div>
                {b.with_doctor && (
                  <div
                    className="entry"
                    style={{
                      background: "var(--status-routine-bg)",
                      borderColor: "var(--status-routine-border)",
                    }}
                  >
                    <EntryHeader e={b.with_doctor} />{" "}
                    <span className="pill routine">with doctor</span>
                    <button
                      className="btn small"
                      onClick={() => act(b.with_doctor!, "mark_done")}
                    >
                      Mark done
                    </button>
                  </div>
                )}
                {b.present_waiting.map((e, i) => (
                  <div
                    key={e.id}
                    className={`entry ${dragId === e.id ? "dragging" : ""}`}
                    draggable={b.mode === "nurse" && !e.fast_tracked}
                    onDragStart={() => setDragId(e.id)}
                    onDragOver={(ev) => ev.preventDefault()}
                    onDrop={() => drop(b, e.id)}
                  >
                    <EntryHeader e={e} />
                    <div className="small-text">{e.chief_complaint ?? "—"}</div>
                    <PriorityChip e={e} />
                    <div className="row" style={{ marginTop: 6 }}>
                      {b.mode === "nurse" && !e.fast_tracked && (
                        <>
                          <button
                            className="btn small ghost"
                            disabled={i === 0}
                            onClick={() => act(e, "move_up")}
                            aria-label="Move up"
                          >
                            Up
                          </button>
                          <button
                            className="btn small ghost"
                            onClick={() => act(e, "move_down")}
                            aria-label="Move down"
                          >
                            Down
                          </button>
                        </>
                      )}
                      <button
                        className="btn small"
                        disabled={!!b.with_doctor}
                        onClick={() => act(e, "mark_with_doctor")}
                      >
                        With doctor
                      </button>
                      {!e.fast_tracked ? (
                        <button className="btn small warn" onClick={() => act(e, "fast_track")}>
                          Fast-track
                        </button>
                      ) : (
                        <button
                          className="btn small secondary"
                          onClick={() => act(e, "return_to_queue")}
                        >
                          Return to queue
                        </button>
                      )}
                      <button className="btn small ghost" onClick={() => setOpen(e.id)}>
                        Open
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <div>
                {b.expected_today_flagged.length > 0 && (
                  <>
                    <h3 className="row" style={{ alignItems: "center", gap: "0.4rem" }}>
                      <AlertTriangleIcon
                        width={16}
                        height={16}
                        style={{ color: "var(--status-urgent-solid)" }}
                      />
                      <span>Expected today (flagged)</span>
                    </h3>
                    {b.expected_today_flagged.map((e) => (
                      <div key={e.id} className="entry alert-amber">
                        <EntryHeader e={e} />
                        <div className="small-text">
                          {e.chief_complaint ?? "—"} ·{" "}
                          {e.presence === "self_reported_arrived"
                            ? "says they are here"
                            : e.presence.replace(/_/g, " ")}
                        </div>
                        <button className="btn small" onClick={() => setOpen(e.id)}>
                          Check in
                        </button>
                      </div>
                    ))}
                  </>
                )}
                <details
                  open={b.booked_not_arrived.some(
                    (e) => e.presence === "self_reported_arrived"
                  )}
                >
                  <summary>
                    <h3 style={{ display: "inline" }}>
                      Booked, not arrived ({b.still_to_come} still to come)
                    </h3>
                  </summary>
                  {b.booked_not_arrived.map((e) => (
                    <div key={e.id} className="entry">
                      <EntryHeader e={e} />
                      <div className="small-text">
                        {e.chief_complaint ?? "—"} ·{" "}
                        {e.presence === "self_reported_arrived"
                          ? "Self-reported arrival"
                          : e.presence.replace(/_/g, " ")}
                      </div>
                      <div className="row">
                        <button className="btn small" onClick={() => setOpen(e.id)}>
                          {e.presence === "self_reported_arrived"
                            ? "Confirm arrival"
                            : "Check in"}
                        </button>
                        <button
                          className="btn small ghost"
                          onClick={() => act(e, "mark_no_show")}
                        >
                          No-show
                        </button>
                      </div>
                    </div>
                  ))}
                </details>
              </div>
            </div>
          </section>
        </>
      )}

      {/* Change Priority Dialog */}
      <Dialog
        open={!!priorityModal}
        onClose={() => !prioritySubmitting && setPriorityModal(null)}
        title="Change Patient Priority"
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => setPriorityModal(null)}
              disabled={prioritySubmitting}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={confirmChangePriority}
              disabled={prioritySubmitting || !priorityModal?.reason.trim()}
              loading={prioritySubmitting}
            >
              Confirm Priority Change
            </Button>
          </>
        }
      >
        <p className="small-text muted">
          Urgency levels affect queue scheduling. All changes are logged with staff identity and rationale.
        </p>
        <Field label="New Priority" required>
          <Select
            value={priorityModal?.priority ?? "same-day"}
            onChange={(e) =>
              setPriorityModal((prev) => (prev ? { ...prev, priority: e.target.value } : null))
            }
            options={[
              { value: "routine", label: "Routine (Standard Token)" },
              { value: "same-day", label: "Same-day (Flagged / Urgent)" },
              { value: "emergency", label: "Emergency (Immediate Attention)" },
            ]}
          />
        </Field>
        <Field label="Clinical Reason" required>
          <textarea
            rows={3}
            placeholder="Document clinical rationale for changing priority..."
            value={priorityModal?.reason ?? ""}
            onChange={(e) =>
              setPriorityModal((prev) => (prev ? { ...prev, reason: e.target.value } : null))
            }
            autoFocus
          />
        </Field>
      </Dialog>

      {/* Send to ER Dialog */}
      <Dialog
        open={!!erModal}
        onClose={() => !erSubmitting && setErModal(null)}
        title="Send Patient to Emergency Room"
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => setErModal(null)}
              disabled={erSubmitting}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={confirmSendToEr}
              disabled={erSubmitting || !erModal?.reason.trim()}
              loading={erSubmitting}
            >
              Transfer to ER
            </Button>
          </>
        }
      >
        <p className="small-text muted">
          This patient will be escalated immediately out of the OPD queue and transferred to the emergency department.
        </p>
        <Field label="Emergency Transfer Reason" required>
          <textarea
            rows={3}
            placeholder="Clinical reason for immediate ER transfer..."
            value={erModal?.reason ?? ""}
            onChange={(e) =>
              setErModal((prev) => (prev ? { ...prev, reason: e.target.value } : null))
            }
            autoFocus
          />
        </Field>
      </Dialog>

      {/* Simulated Scan & Share Dialog */}
      <Dialog
        open={scanModalOpen}
        onClose={() => !scanSubmitting && setScanModalOpen(false)}
        title="Scan & Share Express Registration (Simulation)"
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => setScanModalOpen(false)}
              disabled={scanSubmitting}
            >
              Close
            </Button>
            <Button
              variant="primary"
              onClick={submitScanAndShare}
              disabled={
                scanSubmitting ||
                !scanForm.full_name.trim() ||
                !scanForm.age ||
                !scanForm.abha_address.trim()
              }
              loading={scanSubmitting}
            >
              Process Check-In / Walk-in
            </Button>
          </>
        }
      >
        <Banner variant="info" style={{ marginBottom: "1rem" }}>
          ABDM Simulation: Shares <strong>only demographic profile</strong> (name, age, gender, synthetic ABHA).
          No medical history or health records are shared through Scan &amp; Share.
        </Banner>

        <div style={{ marginBottom: "0.75rem", display: "flex", justifyContent: "flex-end" }}>
          <Button variant="ghost" size="small" onClick={fillDemoScan}>
            Fill Demo Patient
          </Button>
        </div>

        <form onSubmit={submitScanAndShare}>
          <Field label="Synthetic ABHA Address" required hint="Must match format: user@abdm or user@demo">
            <input
              placeholder="e.g. anitha.kumar@abdm"
              value={scanForm.abha_address}
              onChange={(e) => setScanForm({ ...scanForm, abha_address: e.target.value })}
              required
            />
          </Field>
          <Field label="Full Name" required>
            <input
              placeholder="Patient Name"
              value={scanForm.full_name}
              onChange={(e) => setScanForm({ ...scanForm, full_name: e.target.value })}
              required
            />
          </Field>
          <div className="row">
            <Field label="Age" required style={{ flex: 1 }}>
              <input
                type="number"
                min={0}
                max={125}
                value={scanForm.age}
                onChange={(e) => setScanForm({ ...scanForm, age: e.target.value })}
                required
              />
            </Field>
            <Field label="Gender" required style={{ flex: 1 }}>
              <Select
                value={scanForm.gender}
                onChange={(e) => setScanForm({ ...scanForm, gender: e.target.value })}
                options={[
                  { value: "female", label: "Female" },
                  { value: "male", label: "Male" },
                  { value: "other", label: "Other" },
                ]}
              />
            </Field>
          </div>
        </form>

        {scanResult && (
          <Banner variant="success" style={{ marginTop: "1rem" }}>
            <strong>{scanResult.action === "walk_in_registered" ? "Walk-In Registered!" : "Arrival Confirmed!"}</strong>
            <div className="small-text">
              Patient: {scanResult.shared_profile?.name} ({scanResult.shared_profile?.abha_address}) · Token:{" "}
              {scanResult.token_label ?? "issued"}
            </div>
          </Banner>
        )}
      </Dialog>

      {open != null && (
        <EntryDrawer
          entryId={open}
          onClose={() => {
            setOpen(null);
            load();
          }}
        />
      )}
    </div>
  );
}
