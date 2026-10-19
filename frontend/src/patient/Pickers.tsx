import { useEffect, useMemo, useState } from "react";
import { api, fmtDate } from "../shared/api";
import { useI18n } from "../shared/i18n";
import { Card, ErrorBox, Loading } from "../shared/ui";

export type DoctorCard = {
  id: number; name: string; specialty: string; hospital_id: number; hospital_name: string; area: string; distance_km: number | null;
  next_session: { date: string; window_start: string; window_end: string; tokens_left: number } | null;
};
export type SessionRow = { id: number; date: string; label: string; window_start: string; window_end: string; tokens_left: number; bookable: boolean };

export function DoctorList({ doctors, onPick, showDistance = false }: { doctors: DoctorCard[]; onPick: (d: DoctorCard) => void; showDistance?: boolean }) {
  const { t, lang } = useI18n();
  return (
    <div>
      {doctors.map((d) => (
        <Card key={d.id}>
          <div className="spread">
            <strong>{d.name}</strong>
            {showDistance && d.distance_km != null && <span className="pill">{t("book.km", { km: d.distance_km })}</span>}
          </div>
          <div>{d.specialty} · {d.hospital_name}</div>
          <div className="muted small-text">{d.area}</div>
          <div className="small-text">
            {d.next_session
              ? t("book.next_session", { date: fmtDate(d.next_session.date, lang), window: `${d.next_session.window_start}–${d.next_session.window_end}`, left: d.next_session.tokens_left })
              : t("book.no_session")}
          </div>
          <button className="btn block" style={{ marginTop: "0.5rem" }} onClick={() => onPick(d)} disabled={!d.next_session}>{t("sf.choose")}</button>
        </Card>
      ))}
    </div>
  );
}

export function SessionPicker({ doctorId, onPick, busy }: { doctorId: number; onPick: (s: SessionRow) => void; busy?: boolean }) {
  const { t, lang } = useI18n();
  const [rows, setRows] = useState<SessionRow[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [day, setDay] = useState<string | null>(null);
  useEffect(() => { api<SessionRow[]>(`/catalog/doctors/${doctorId}/sessions`).then(setRows).catch(setErr); }, [doctorId]);
  const days = useMemo(() => Array.from(new Set((rows ?? []).map((r) => r.date))), [rows]);
  useEffect(() => { if (!day && days.length) setDay(days.find((d) => rows!.some((r) => r.date === d && r.bookable && r.tokens_left > 0)) ?? days[0]); }, [days]); // eslint-disable-line react-hooks/exhaustive-deps
  if (err) return <ErrorBox error={err} />;
  if (!rows) return <Loading />;
  return (
    <div>
      <h2>{t("book.choose_session")}</h2>
      <div className="chips">
        {days.map((d) => (
          <button key={d} className={`chip ${d === day ? "on" : ""}`} onClick={() => setDay(d)}>{fmtDate(d, lang)}</button>
        ))}
      </div>
      {rows.filter((r) => r.date === day).map((s) => {
        const ok = s.bookable && s.tokens_left > 0;
        return (
          <Card key={s.id}>
            <div className="spread">
              <strong>{t(`book.${s.label}`)} {s.window_start}–{s.window_end}</strong>
              <span className="pill">{ok ? t("book.tokens_left", { left: s.tokens_left }) : t("book.full")}</span>
            </div>
            <button className="btn block" style={{ marginTop: "0.5rem" }} disabled={!ok || busy} onClick={() => onPick(s)}>{t("common.next")}</button>
          </Card>
        );
      })}
    </div>
  );
}
