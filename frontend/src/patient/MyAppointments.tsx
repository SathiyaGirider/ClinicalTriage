import { useCallback, useEffect, useState } from "react";
import { api, fmtDate, fmtTime, post } from "../shared/api";
import { useI18n } from "../shared/i18n";
import { Card, ErrorBox, Loading } from "../shared/ui";
import { MicButton } from "../shared/voice";
import { Directions, type Appointment } from "./Outcomes";
import { SessionPicker } from "./Pickers";

type Status = Appointment & { now_serving: string | null; is_today?: boolean };

function ImHere({ appt, onDone }: { appt: Appointment; onDone: () => void }) {
  const { t } = useI18n();
  const [change, setChange] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const send = async (c: string, body?: string) => {
    setBusy(true);
    try { await post(`/booking/${appt.id}/arrived`, { change: c, text: body || undefined }); onDone(); } catch (e) { setErr(e); } finally { setBusy(false); }
  };
  return (
    <div className="card">
      <h3>{t("appt.change_q")}</h3>
      {!change && (
        <div className="grid">
          <button className="btn" disabled={busy} onClick={() => send("none")}>{t("appt.no_change")}</button>
          <button className="btn secondary" disabled={busy} onClick={() => send("better")}>{t("appt.better")}</button>
          <button className="btn warn" disabled={busy} onClick={() => setChange("worse")}>{t("appt.worse")}</button>
          <button className="btn warn" disabled={busy} onClick={() => setChange("new_symptom")}>{t("appt.new_symptom")}</button>
        </div>
      )}
      {change && (
        <form onSubmit={(e) => { e.preventDefault(); send(change, text); }}>
          <label className="field">{t("appt.describe")}<textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} /></label>
          <div className="row">
            <MicButton onText={(s) => setText((x) => (x ? `${x} ${s}` : s))} />
            <button className="btn" style={{ flex: 1 }} disabled={busy || !text.trim()}>{t("appt.send")}</button>
          </div>
        </form>
      )}
      <ErrorBox error={err} />
    </div>
  );
}

function LiveCard({ appt, reload }: { appt: Appointment; reload: () => void }) {
  const { t, lang } = useI18n();
  const [st, setSt] = useState<Status | null>(null);
  const [asking, setAsking] = useState(false);
  const [moving, setMoving] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const poll = useCallback(() => api<Status>(`/booking/${appt.id}/status`).then(setSt).catch(setErr), [appt.id]);
  useEffect(() => {
    poll();
    const h = setInterval(poll, 10000); // live status: every 10 seconds
    return () => clearInterval(h);
  }, [poll]);
  const a = st ?? (appt as Status);
  const isToday = !!a.is_today;
  const cancel = async () => {
    if (!window.confirm(t("appt.cancel_confirm"))) return;
    try { await post(`/booking/${appt.id}/cancel`); reload(); } catch (e) { setErr(e); }
  };
  const reschedule = async (sessionId: number) => {
    try { await post(`/booking/${appt.id}/reschedule`, { session_id: sessionId }); setMoving(false); reload(); } catch (e) { setErr(e); }
  };
  return (
    <Card className={a.state === "with_doctor" ? "ok" : ""}>
      <div className="spread">
        <div>
          <div className="muted small-text">{t("appt.your_token")}</div>
          <div className="token">{a.token_label ?? "—"}</div>
        </div>
        {a.now_serving !== undefined && (
          <div style={{ textAlign: "right" }}>
            <div className="muted small-text">{t("appt.now_serving")}</div>
            <div className="token" style={{ fontSize: "1.8rem" }}>{a.now_serving ?? "—"}</div>
          </div>
        )}
      </div>
      <p>
        <strong>{t(`appt.state.${a.state}`)}</strong><br />
        {a.doctor?.name} · {a.doctor?.specialty}<br />
        {a.hospital?.name} · {fmtDate(a.date, lang)} {a.session ? `· ${t(`book.${a.session.label}`)} ${a.session.window_start}–${a.session.window_end}` : ""}
      </p>
      {a.type === "walk_in" && !a.token_label && <p className="notice">{t("appt.walkin_note")}</p>}
      {a.est_call_from && a.state !== "with_doctor" && (
        <p>{t("out.est")}: <strong>{fmtTime(a.est_call_from)} – {fmtTime(a.est_call_to)}</strong> <span className="pill">{t("common.approximate")}</span></p>
      )}
      <div className="row">
        {a.hospital && <Directions h={a.hospital} />}
        {isToday && ["booked", "called_absent", "expected_today"].includes(a.state) && !asking && (
          <button className="btn" onClick={() => setAsking(true)}>🙋 {t("appt.im_here")}</button>
        )}
        {a.state === "booked" && a.status === "booked" && <button className="btn ghost small" onClick={() => setMoving((m) => !m)}>{t("appt.reschedule")}</button>}
        {["booked", "expected_today"].includes(a.status) && <button className="btn ghost small" onClick={cancel}>{t("appt.cancel")}</button>}
      </div>
      {a.state === "arrived_unconfirmed" && <p className="notice">{t("appt.waiting_nurse")}</p>}
      {asking && <ImHere appt={appt} onDone={() => { setAsking(false); poll(); }} />}
      {moving && a.doctor && <SessionPicker doctorId={a.doctor.id} onPick={(s) => reschedule(s.id)} />}
      <ErrorBox error={err} />
    </Card>
  );
}

export default function MyAppointments() {
  const { t, lang } = useI18n();
  const [data, setData] = useState<{ upcoming: Appointment[]; past: Appointment[] } | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const load = () => api("/booking/mine").then(setData).catch(setErr);
  useEffect(() => { load(); }, []);
  if (err) return <ErrorBox error={err} onRetry={() => { setErr(null); load(); }} />;
  if (!data) return <Loading />;
  return (
    <div>
      <h1>{t("nav.appointments")}</h1>
      <h2>{t("appt.upcoming")}</h2>
      {data.upcoming.length === 0 && <p className="muted">{t("appt.none")}</p>}
      {data.upcoming.map((a) => <LiveCard key={a.id} appt={a} reload={load} />)}
      <h2>{t("appt.past")}</h2>
      {data.past.map((a) => (
        <Card key={a.id}>
          <div className="spread"><strong>{a.token_label ?? "—"}</strong><span className="pill">{t(`appt.state.${a.state}`)}</span></div>
          <div>{a.doctor?.name} · {a.hospital?.name} · {fmtDate(a.date, lang)}</div>
        </Card>
      ))}
    </div>
  );
}
