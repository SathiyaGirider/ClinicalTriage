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
  const [devScenarios, setDevScenarios] = useState<{ file: string; id: string; title: string }[] | null>(null);
  const [selectedScenario, setSelectedScenario] = useState<string>("scenario-04.json");

  useEffect(() => {
    const area = me?.area ? `?area=${encodeURIComponent(me.area)}` : "";
    api(`/catalog/hospitals${area}`).then(setHospitals).catch(setErr);
    api<string[]>("/catalog/specialties").then(setSpecialties).catch(setErr);
    api<{ dev_endpoints?: boolean }>("/config/public")
      .then((cfg) => {
        if (cfg.dev_endpoints) {
          api<{ file: string; id: string; title: string }[]>("/pipeline/scenarios").then(setDevScenarios).catch(() => undefined);
        }
      })
      .catch(() => undefined);
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

  const skipQuestions = async () => {
    if (!holdId) return;
    setStep("submitting");
    setBusy(true);
    try {
      const r = await post<{ advice: Advice; intake_id: number; appointment: Appointment }>("/pipeline/skip-intake", { hold_id: holdId });
      setAdvice(r.advice);
      if (r.appointment) {
        setAppt(r.appointment);
        setStep("routine");
      }
    } catch (e) {
      setErr(e);
      setStep("intake");
    } finally {
      setBusy(false);
    }
  };

  const loadDevScenario = async () => {
    if (!selectedScenario) return;
    setStep("submitting");
    try {
      const r = await post<{ advice: Advice; intake_id: number }>("/pipeline/load-scenario", {
        scenario: selectedScenario,
        hold_id: holdId,
      });
      setAdvice(r.advice);
      if (r.advice.outcome === "seek_emergency_now") { setHoldId(null); return setStep("emergency"); }
      if (r.advice.outcome === "staff_will_check_on_you") { setHoldId(null); return setStep("concerning"); }
      if (holdId) {
        const f = await post("/booking/finalize", { hold_id: holdId, intake_id: r.intake_id });
        if (f.appointment) { setAppt(f.appointment); return setStep("routine"); }
      }
      setStep("concerning");
    } catch (e) {
      setErr(e);
      setStep("intake");
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
          <div className="banner banner-info" style={{ marginBottom: "1rem" }} role="note">
            <span><strong>Automated Assistant Notice:</strong> An automated tool helps prepare information for your care team. A nurse or doctor makes every decision. You can skip these questions and speak directly to clinical staff upon arrival.</span>
          </div>

          <div className="row spread" style={{ marginBottom: "1rem", gap: "0.5rem", alignItems: "center" }}>
            <p className="notice" style={{ margin: 0, flex: 1 }}>{t("book.hold_note")}</p>
            <button type="button" className="btn small outline" onClick={skipQuestions} disabled={busy}>
              Skip questions
            </button>
          </div>

          {devScenarios && devScenarios.length > 0 && (
            <div style={{ marginBottom: "1rem", padding: "0.75rem", background: "#f8fafc", borderRadius: "6px", border: "1px dashed #cbd5e1" }}>
              <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.5rem", color: "#475569" }}>Developer Demo: Load Scenario</div>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <select value={selectedScenario} onChange={(e) => setSelectedScenario(e.target.value)} style={{ flex: 1, padding: "0.4rem", borderRadius: "4px", border: "1px solid #cbd5e1" }}>
                  {devScenarios.map((s) => (
                    <option key={s.file} value={s.file}>{s.file}: {s.id}</option>
                  ))}
                </select>
                <button type="button" className="btn small secondary" onClick={loadDevScenario}>Load</button>
              </div>
            </div>
          )}
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

