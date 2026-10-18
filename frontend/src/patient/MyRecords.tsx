import { useEffect, useState } from "react";
import { api, fmtDate } from "../shared/api";
import { useI18n } from "../shared/i18n";
import { Card, ErrorBox, Loading } from "../shared/ui";

type Visit = { id: number; date: string; doctor_name: string; specialty: string; hospital_name: string; diagnosis_text: string; follow_up_date: string | null;
  prescriptions: { drug: string; dose: string; frequency: string; duration: string; instructions: string }[] };

// Shown exactly as the doctor wrote it. No AI commentary.
export default function MyRecords() {
  const { t, lang } = useI18n();
  const [visits, setVisits] = useState<Visit[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => { api("/me/records").then((r) => setVisits(r.visits)).catch(setErr); }, []);
  if (err) return <ErrorBox error={err} />;
  if (!visits) return <Loading />;
  return (
    <div>
      <h1>{t("rec.title")}</h1>
      {visits.length === 0 && <p className="muted">{t("rec.none")}</p>}
      {visits.map((v) => (
        <Card key={v.id}>
          <div className="spread"><strong>{fmtDate(v.date, lang)}</strong><span className="muted small-text">{v.hospital_name}</span></div>
          <div>{v.doctor_name} · {v.specialty}</div>
          <h3>{t("rec.diagnosis")}</h3>
          <p>{v.diagnosis_text}</p>
          {v.prescriptions.length > 0 && (
            <>
              <h3>{t("rec.prescription")}</h3>
              {v.prescriptions.map((p, i) => (
                <div key={i} className="entry">
                  <strong>{p.drug}</strong>
                  <div className="small-text">{t("rec.dose")}: {p.dose} · {t("rec.frequency")}: {p.frequency} · {t("rec.duration")}: {p.duration}</div>
                  {p.instructions && <div className="small-text">{t("rec.instructions")}: {p.instructions}</div>}
                </div>
              ))}
            </>
          )}
          {v.follow_up_date && <p className="small-text">{t("rec.follow_up")}: {fmtDate(v.follow_up_date, lang)}</p>}
        </Card>
      ))}
      <p className="notice">{t("rec.footer")}</p>
    </div>
  );
}
