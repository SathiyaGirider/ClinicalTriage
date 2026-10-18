import { useEffect, useState } from "react";
import { api, ApiError, post } from "../shared/api";
import { useAuth } from "../shared/auth";
import { useI18n } from "../shared/i18n";
import { Card, ErrorBox, Loading } from "../shared/ui";
import IntakeWizard, { type SessionView } from "./IntakeWizard";
import { ConcerningOutcome, EmergencyScreen, RoutineOutcome, useEmergencyNumbers, type Advice, type Appointment, type Hospital } from "./Outcomes";
import { DoctorList, SessionPicker, type DoctorCard, type SessionRow } from "./Pickers";

type Step = "hospital" | "specialty" | "doctor" | "session" | "intake" | "submitting" | "routine" | "concerning" | "emergency";

export default function BookingFlow() {
  const { t, lang } = useI18n();
  const { me } = useAuth();
  const numbers = useEmergencyNumbers();
  const [step, setStep] = useState<Step>("hospital");
  const [hospitals, setHospitals] = useState<(Hospital & { distance_km: number | null })[] | null>(null);
  const [hospital, setHospital] = useState<Hospital | null>(null);
  const [specialties, setSpecialties] = useState<string[]>([]);
  const [specialty, setSpecialty] = useState<string | null>(null);
  const [doctors, setDoctors] = useState<DoctorCard[] | null>(null);
  const [doctor, setDoctor] = useState<DoctorCard | null>(null);
  const [holdId, setHoldId] = useState<number | null>(null);
  const [advice, setAdvice] = useState<Advice | null>(null);
  const [appt, setAppt] = useState<Appointment | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const area = me?.area ? `?area=${encodeURIComponent(me.area)}` : "";
    api(`/catalog/hospitals${area}`).then(setHospitals).catch(setErr);
    api<string[]>("/catalog/specialties").then(setSpecialties).catch(setErr);
  }, [me?.area]);

  // Release the hold if the patient leaves the flow before finalising.
  useEffect(() => () => { if (holdId && !appt) post(`/booking/${holdId}/release`).catch(() => undefined); }, [holdId, appt]);

  const chooseDoctorList = async (spec: string) => {
    setSpecialty(spec);
    setDoctors(null);
    setStep("doctor");
    try { setDoctors(await api(`/catalog/doctors?specialty=${encodeURIComponent(spec)}&hospital_id=${hospital!.id}`)); } catch (e) { setErr(e); }
  };
  const pickSession = async (s: SessionRow) => {
    setBusy(true);
    setErr(null);
    try {
      const r = await post("/booking/hold", { session_id: s.id });
      setHoldId(r.hold_id);
      setStep("intake");
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };
  const finished = async (sessionId: string) => {
    setStep("submitting");
    try {
      const r = await post<{ advice: Advice; intake_id: number }>("/pipeline/submit", { intake_session_id: sessionId, hold_id: holdId });
      setAdvice(r.advice);
      if (r.advice.outcome === "seek_emergency_now") { setHoldId(null); return setStep("emergency"); }
      if (r.advice.outcome === "staff_will_check_on_you") { setHoldId(null); return setStep("concerning"); }
      const f = await post("/booking/finalize", { hold_id: holdId, intake_id: r.intake_id });
      if (f.appointment) { setAppt(f.appointment); setStep("routine"); }
      else setStep("concerning");
    } catch (e) {
      setErr(e);
      if (e instanceof ApiError && e.status === 410) { setHoldId(null); setStep("session"); }
      else setStep("intake");
    }
  };

  if (step === "emergency") return <EmergencyScreen hospital={hospital} numbers={numbers} />;
  return (
    <div>
      {step !== "routine" && step !== "concerning" && <h1>{t("home.book")}</h1>}
      <ErrorBox error={err instanceof ApiError && err.status === 410 ? new Error(t("book.hold_expired")) : err} />
      {step === "hospital" && (!hospitals ? <Loading /> : (
        <>
          <h2>{t("book.choose_hospital")}</h2>
          {hospitals.map((h) => (
            <Card key={h.id}>
              <strong>{h.name}</strong><br /><span className="muted small-text">{h.area} · {h.address}</span>
              <button className="btn block" style={{ marginTop: "0.5rem" }} onClick={() => { setHospital(h); setStep("specialty"); }}>{t("common.next")}</button>
            </Card>
          ))}
        </>
      ))}
      {step === "specialty" && (
        <>
          <h2>{t("book.choose_specialty")}</h2>
          <div className="chips">{specialties.map((s) => <button key={s} className="chip" onClick={() => chooseDoctorList(s)}>{s}</button>)}</div>
          <button className="btn ghost" onClick={() => setStep("hospital")}>{t("common.back")}</button>
        </>
      )}
      {step === "doctor" && (
        <>
          <h2>{t("book.choose_doctor")} · {specialty}</h2>
          {!doctors ? <Loading /> : <DoctorList doctors={doctors} onPick={(d) => { setDoctor(d); setStep("session"); }} />}
          <button className="btn ghost" onClick={() => setStep("specialty")}>{t("common.back")}</button>
        </>
      )}
      {step === "session" && doctor && (
        <>
          <p><strong>{doctor.name}</strong> · {doctor.specialty}</p>
          <SessionPicker doctorId={doctor.id} onPick={pickSession} busy={busy} />
          <button className="btn ghost" onClick={() => setStep("doctor")}>{t("common.back")}</button>
        </>
      )}
      {step === "intake" && (
        <>
          <p className="notice">{t("book.hold_note")}</p>
          <IntakeWizard start={() => post<SessionView>("/intake/session/start", { mode: "booking", language: lang })} onFinished={finished} />
        </>
      )}
      {step === "submitting" && <Loading />}
      {step === "routine" && appt && <RoutineOutcome appt={appt} />}
      {step === "concerning" && advice && (
        <ConcerningOutcome intakeId={advice.intake_id} doctorId={doctor?.id} hospitalId={hospital?.id} specialty={doctor?.specialty}
          onBooked={(a) => { setAppt(a); setStep("routine"); }} />
      )}
    </div>
  );
}
