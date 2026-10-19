import { useEffect, useState } from "react";
import { api, post } from "../shared/api";
import { useAuth } from "../shared/auth";
import { useI18n } from "../shared/i18n";
import { ErrorBox, Loading } from "../shared/ui";
import IntakeWizard, { type SessionView } from "./IntakeWizard";
import { ConcerningOutcome, EmergencyScreen, RoutineOutcome, useEmergencyNumbers, type Advice, type Appointment } from "./Outcomes";
import { DoctorList, SessionPicker, type DoctorCard, type SessionRow } from "./Pickers";

type Step = "intake" | "submitting" | "doctors" | "session" | "routine" | "concerning" | "emergency";

export default function SymptomFlow() {
  const { t, lang } = useI18n();
  const { me } = useAuth();
  const numbers = useEmergencyNumbers();
  const [step, setStep] = useState<Step>("intake");
  const [advice, setAdvice] = useState<Advice | null>(null);
  const [doctors, setDoctors] = useState<DoctorCard[] | null>(null);
  const [doctor, setDoctor] = useState<DoctorCard | null>(null);
  const [area, setArea] = useState(me?.area ?? "");
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [locNote, setLocNote] = useState(false);
  const [appt, setAppt] = useState<Appointment | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const loadDoctors = async (spec: string) => {
    const qs = new URLSearchParams({ specialty: spec });
    if (coords) { qs.set("lat", String(coords.lat)); qs.set("lon", String(coords.lon)); }
    else if (area) qs.set("area", area);
    try { setDoctors(await api(`/catalog/doctors?${qs}`)); } catch (e) { setErr(e); }
  };
  useEffect(() => { if (advice?.suggested_department && step === "doctors") loadDoctors(advice.suggested_department); }, [coords, area, step]); // eslint-disable-line react-hooks/exhaustive-deps

  const finished = async (sessionId: string) => {
    setStep("submitting");
    try {
      const r = await post<{ advice: Advice }>("/pipeline/submit", { intake_session_id: sessionId });
      setAdvice(r.advice);
      setStep(r.advice.outcome === "seek_emergency_now" ? "emergency" : "doctors");
    } catch (e) { setErr(e); setStep("intake"); }
  };
  const useLocation = () => {
    if (!navigator.geolocation) return setLocNote(true);
    navigator.geolocation.getCurrentPosition((p) => setCoords({ lat: p.coords.latitude, lon: p.coords.longitude }), () => setLocNote(true), { timeout: 8000 });
  };
  const pickDoctor = (d: DoctorCard) => {
    setDoctor(d);
    setStep(advice!.outcome === "staff_will_check_on_you" ? "concerning" : "session");
  };
  const pickSession = async (s: SessionRow) => {
    setBusy(true);
    setErr(null);
    try {
      const h = await post("/booking/hold", { session_id: s.id });
      // Reuse the intake already collected: the server applies the same outcome logic at finalise.
      const f = await post("/booking/finalize", { hold_id: h.hold_id, intake_id: advice!.intake_id });
      if (f.appointment) { setAppt(f.appointment); setStep("routine"); } else setStep("concerning");
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };

  if (step === "emergency") return <EmergencyScreen numbers={numbers} />;
  return (
    <div>
      {step === "intake" && <h1>{t("sf.title")}</h1>}
      <ErrorBox error={err} />
      {step === "intake" && <IntakeWizard start={() => post<SessionView>("/intake/session/start", { mode: "symptom_first", language: lang })} onFinished={finished} />}
      {step === "submitting" && <Loading />}
      {step === "doctors" && advice && (
        <>
          <div className="card ok">
            <div className="muted">{t("sf.usually_seen")}</div>
            <strong style={{ fontSize: "1.3rem" }}>{advice.suggested_department}</strong>
          </div>
          {advice.outcome === "staff_will_check_on_you" && <p className="notice">⚠️ {t("out.concern_title")}. {t("out.tell_desk")}</p>}
          <h2>{t("sf.near_you")}</h2>
          <div className="row">
            <button className="btn secondary small" onClick={useLocation}>📍 {t("sf.use_location")}</button>
            <label className="field" style={{ flex: 1, margin: 0 }}>
              <span className="sr-only">{t("sf.area")}</span>
              <input type="text" placeholder={t("sf.area")} value={area} onChange={(e) => { setCoords(null); setArea(e.target.value); }} />
            </label>
          </div>
          {locNote && <p className="muted small-text">{t("sf.location_denied")}</p>}
          {!doctors ? <Loading /> : <DoctorList doctors={doctors} onPick={pickDoctor} showDistance />}
        </>
      )}
      {step === "session" && doctor && (
        <>
          <p><strong>{doctor.name}</strong> · {doctor.specialty} · {doctor.hospital_name}</p>
          <SessionPicker doctorId={doctor.id} onPick={pickSession} busy={busy} />
          <button className="btn ghost" onClick={() => setStep("doctors")}>{t("common.back")}</button>
        </>
      )}
      {step === "concerning" && advice && (
        <ConcerningOutcome intakeId={advice.intake_id} doctorId={doctor?.id} hospitalId={doctor?.hospital_id} specialty={advice.suggested_department ?? undefined}
          onBooked={(a) => { setAppt(a); setStep("routine"); }} />
      )}
      {step === "routine" && appt && <RoutineOutcome appt={appt} />}
    </div>
  );
}
