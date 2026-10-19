import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtDate, fmtTime, getToken, mapsLink, post } from "../shared/api";
import { useI18n } from "../shared/i18n";
import { Card, ErrorBox, Loading } from "../shared/ui";

export type Hospital = { id: number; name: string; address: string; area: string; er_phone: string; er_note?: string; walk_in_window_text: string; opd_hours?: string };
export type Appointment = {
  id: number; type: string; status: string; date: string; token_label: string | null; est_call_from: string | null; est_call_to: string | null;
  doctor: { id: number; name: string; specialty: string } | null; hospital: Hospital | null;
  session: { id: number; label: string; window_start: string; window_end: string } | null; state: string; intake_id: number | null;
};
export type Advice = { outcome: "wait_in_queue" | "staff_will_check_on_you" | "seek_emergency_now"; title: string; message: string; department_text?: string | null; suggested_department?: string | null; intake_id: number };

export function Directions({ h }: { h: Hospital }) {
  const { t } = useI18n();
  return (
    <a className="btn secondary small" href={mapsLink(h.name, h.address)} target="_blank" rel="noreferrer">
      🧭 {t("common.directions")}
    </a>
  );
}

async function downloadIcs(id: number) {
  const res = await fetch(`/booking/${id}/ics`, { headers: { Authorization: `Bearer ${getToken()}` } });
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `lifeline-${id}.ics`;
  a.click();
}

export function RoutineOutcome({ appt }: { appt: Appointment }) {
  const { t, lang } = useI18n();
  const s = appt.session;
  return (
    <div>
      <h1>✅ {t("out.routine_title")}</h1>
      <Card className="ok">
        <div className="muted">{t("out.token")}</div>
        <div className="token" data-testid="token">{appt.token_label}</div>
        <p>
          <strong>{appt.doctor?.name}</strong> · {appt.doctor?.specialty}<br />
          {appt.hospital?.name}<br />
          {fmtDate(appt.date, lang)} · {s ? `${t(`book.${s.label}`)} ${s.window_start}–${s.window_end}` : ""}
        </p>
        {appt.est_call_from && (
          <p>
            <strong>{t("out.est")}:</strong> {fmtTime(appt.est_call_from)} – {fmtTime(appt.est_call_to)} <span className="pill">{t("common.approximate")}</span>
          </p>
        )}
        <p className="small-text">{appt.hospital?.address}</p>
        <div className="row">
          {appt.hospital && <Directions h={appt.hospital} />}
          <button className="btn secondary small" onClick={() => downloadIcs(appt.id)}>📅 {t("out.ics")}</button>
        </div>
      </Card>
      <p className="notice">{t("out.arrive_note")}</p>
      <Link className="btn block" to="/patient/appointments">{t("out.see_appointments")}</Link>
    </div>
  );
}

export function EmergencyScreen({ hospital, numbers }: { hospital?: Hospital | null; numbers: string[] }) {
  const { t } = useI18n();
  useEffect(() => { window.scrollTo(0, 0); }, []);
  return (
    <div className="emergency-screen" role="alertdialog" aria-labelledby="em-title">
      <div className="inner">
        <div style={{ fontSize: "3rem" }} aria-hidden>🚑</div>
        <h1 id="em-title">{t("out.emergency_title")}</h1>
        {hospital && (
          <div className="card">
            <h2>{t("out.er_address")}</h2>
            <p><strong>{hospital.name}</strong><br />{hospital.address}</p>
            {hospital.er_note && <p className="small-text">{hospital.er_note}</p>}
            <div className="row">
              <a className="btn" href={`tel:${hospital.er_phone.replace(/[^0-9+]/g, "")}`}>📞 {t("out.call")} {hospital.er_phone}</a>
              <a className="btn" href={mapsLink(hospital.name, hospital.address)} target="_blank" rel="noreferrer">🧭 {t("common.directions")}</a>
            </div>
          </div>
        )}
        <div className="card">
          <h2>{t("out.emergency_numbers")}</h2>
          <div className="row">
            {numbers.map((n) => (
              <a key={n} className="btn" href={`tel:${n}`} style={{ fontSize: "1.4rem" }}>📞 {n}</a>
            ))}
          </div>
        </div>
        <p>{t("out.no_booking")}</p>
        <Link className="btn" to="/patient">{t("nav.home")}</Link>
      </div>
    </div>
  );
}

type TodaySession = { id: number; label: string; window_start: string; window_end: string; urgent_tokens_left: number; doctor: { id: number; name: string; specialty: string } };
type Today = { sessions: TodaySession[]; scope: string; hospital: Hospital | null; walk_in_fallback: { walk_in_window_text: string; opd_hours: string } | null };

export function ConcerningOutcome({ intakeId, doctorId, hospitalId, specialty, onBooked }: {
  intakeId: number; doctorId?: number; hospitalId?: number; specialty?: string; onBooked: (a: Appointment) => void;
}) {
  const { t } = useI18n();
  const [today, setToday] = useState<Today | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [walkIn, setWalkIn] = useState<Appointment | null>(null);
  const load = () => {
    const qs = new URLSearchParams();
    if (doctorId) qs.set("doctor_id", String(doctorId));
    if (hospitalId) qs.set("hospital_id", String(hospitalId));
    if (specialty) qs.set("specialty", specialty);
    api<Today>(`/booking/today-sessions?${qs}`).then(setToday).catch(setErr);
  };
  useEffect(load, [doctorId, hospitalId, specialty]); // eslint-disable-line react-hooks/exhaustive-deps
  const pick = async (sid: number) => {
    setBusy(true);
    try {
      const r = await post("/booking/finalize", { mode: "same_day", session_id: sid, intake_id: intakeId });
      onBooked(r.appointment);
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };
  const willCome = async () => {
    if (!today?.hospital) return;
    setBusy(true);
    try {
      const r = await post("/booking/walk-in-intent", { intake_id: intakeId, hospital_id: today.hospital.id, doctor_id: doctorId });
      setWalkIn(r.appointment);
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };
  return (
    <div>
      <h1>⚠️ {t("out.concern_title")}</h1>
      <p className="notice">{t("out.tell_desk")}</p>
      <ErrorBox error={err} onRetry={() => { setErr(null); load(); }} />
      {!today ? <Loading /> : (
        <>
          {today.sessions.length > 0 && (
            <>
              <h2>{today.scope === "same_doctor" ? t("out.today_sessions") : t("out.other_doctors")}</h2>
              {today.sessions.map((s) => (
                <Card key={s.id}>
                  <strong>{s.doctor.name}</strong> · {s.doctor.specialty}<br />
                  {t(`book.${s.label}`)} {s.window_start}–{s.window_end} · {t("book.tokens_left", { left: s.urgent_tokens_left })}
                  <button className="btn block" style={{ marginTop: "0.5rem" }} disabled={busy} onClick={() => pick(s.id)}>{t("out.pick_session")}</button>
                </Card>
              ))}
            </>
          )}
          {today.sessions.length === 0 && today.walk_in_fallback && !walkIn && (
            <Card className="amber">
              <p>{t("out.no_today")}</p>
              <p><strong>{today.walk_in_fallback.walk_in_window_text}</strong><br />{today.walk_in_fallback.opd_hours}</p>
              <button className="btn block" disabled={busy} onClick={willCome}>{t("out.will_come")}</button>
            </Card>
          )}
          {walkIn && <p className="notice">{t("out.walkin_done")}</p>}
          {today.hospital && (
            <Card>
              <strong>{today.hospital.name}</strong><br />
              <span className="small-text">{today.hospital.address}</span>
              <div className="row" style={{ marginTop: "0.5rem" }}><Directions h={today.hospital} /></div>
            </Card>
          )}
          {walkIn && <Link className="btn block" to="/patient/appointments">{t("out.see_appointments")}</Link>}
        </>
      )}
    </div>
  );
}

let _numbers: string[] | null = null;
export function useEmergencyNumbers() {
  const [n, setN] = useState<string[]>(_numbers ?? ["112", "108"]);
  useEffect(() => {
    if (_numbers) return;
    api("/config/public").then((c) => { _numbers = c.emergency_numbers; setN(c.emergency_numbers); }).catch(() => undefined);
  }, []);
  return n;
}
