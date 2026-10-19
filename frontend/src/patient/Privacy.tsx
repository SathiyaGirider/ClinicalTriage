import { useEffect, useState } from "react";
import { api, fmtDate, put } from "../shared/api";
import { useAuth } from "../shared/auth";
import { useI18n } from "../shared/i18n";
import { Card, ErrorBox, Loading } from "../shared/ui";

export default function Privacy() {
  const { t, lang } = useI18n();
  const { me, refresh } = useAuth();
  const [consent, setConsent] = useState<boolean>(!!me?.share_history_consent);
  const [log, setLog] = useState<{ viewer: string; hospital: string; what: string; ts: string }[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => { api("/me/access-log").then(setLog).catch(setErr); }, []);
  const toggle = async (v: boolean) => {
    setConsent(v);
    try { await put("/me/consent", { share_history_consent: v }); refresh(); } catch (e) { setErr(e); setConsent(!v); }
  };
  return (
    <div>
      <h1>{t("priv.title")}</h1>
      <Card>
        <label className="spread" style={{ fontWeight: 600 }}>
          {t("priv.consent")}
          <input type="checkbox" role="switch" checked={consent} onChange={(e) => toggle(e.target.checked)} style={{ width: 32, height: 32 }} />
        </label>
        <p className="muted">{t("priv.explain")}</p>
      </Card>
      <h2>{t("priv.log")}</h2>
      <ErrorBox error={err} />
      {!log ? <Loading /> : log.length === 0 ? <p className="muted">{t("priv.log_none")}</p> : log.map((r, i) => (
        <Card key={i}>{t("priv.log_row", { viewer: r.viewer, hospital: r.hospital, what: r.what, date: `${fmtDate(r.ts, lang)} ${new Date(r.ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}` })}</Card>
      ))}
    </div>
  );
}
