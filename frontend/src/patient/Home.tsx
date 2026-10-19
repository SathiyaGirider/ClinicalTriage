import { Link } from "react-router-dom";
import { useAuth } from "../shared/auth";
import { LanguageSwitch, useI18n } from "../shared/i18n";

export default function Home() {
  const { me } = useAuth();
  const { t } = useI18n();
  return (
    <div>
      <h1>{t("home.hello", { name: me?.full_name ?? "" })}</h1>
      <Link to="/patient/book" className="big-card">
        <span className="icon" aria-hidden>📅</span>
        <strong>{t("home.book")}</strong>
        <span className="muted">{t("home.book_sub")}</span>
      </Link>
      <Link to="/patient/symptoms" className="big-card">
        <span className="icon" aria-hidden>🤔</span>
        <strong>{t("home.symptoms")}</strong>
        <span className="muted">{t("home.symptoms_sub")}</span>
      </Link>
      <div className="grid">
        <Link className="btn secondary" to="/patient/appointments">🎫 {t("nav.appointments")}</Link>
        <Link className="btn secondary" to="/patient/records">📄 {t("nav.records")}</Link>
        <Link className="btn secondary" to="/patient/privacy">🔒 {t("nav.privacy")}</Link>
        <Link className="btn secondary" to="/patient/profile">👤 {t("nav.profile")}</Link>
        <div className="row"><span>🌐 {t("common.language")}:</span> <LanguageSwitch /></div>
      </div>
    </div>
  );
}
