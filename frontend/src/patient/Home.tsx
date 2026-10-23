import { Link } from "react-router-dom";
import { useAuth } from "../shared/auth";
import { CalendarIcon, ClockIcon, HospitalIcon } from "../shared/icons";
import { LanguageSwitch, useI18n } from "../shared/i18n";

export default function Home() {
  const { me } = useAuth();
  const { t } = useI18n();
  return (
    <div className="patient-home">
      <div className="spread" style={{ marginBottom: "1.5rem" }}>
        <h1>{t("home.hello", { name: me?.full_name ?? "" })}</h1>
        <div className="row" style={{ alignItems: "center" }}>
          <span className="small-text muted">{t("common.language")}:</span>
          <LanguageSwitch />
        </div>
      </div>

      <div className="home-cards-grid">
        <Link to="/patient/book" className="big-card">
          <div className="icon-wrap" aria-hidden="true">
            <CalendarIcon width={24} height={24} />
          </div>
          <div>
            <strong>{t("home.book")}</strong>
            <span className="muted small-text">{t("home.book_sub")}</span>
          </div>
        </Link>

        <Link to="/patient/symptoms" className="big-card">
          <div className="icon-wrap" aria-hidden="true">
            <HospitalIcon width={24} height={24} />
          </div>
          <div>
            <strong>{t("home.symptoms")}</strong>
            <span className="muted small-text">{t("home.symptoms_sub")}</span>
          </div>
        </Link>
      </div>

      <div className="home-nav-grid">
        <Link className="btn secondary" to="/patient/appointments">
          <ClockIcon width={18} height={18} />
          <span>{t("nav.appointments")}</span>
        </Link>
        <Link className="btn secondary" to="/patient/records">
          <span>{t("nav.records")}</span>
        </Link>
        <Link className="btn secondary" to="/patient/privacy">
          <span>{t("nav.privacy")}</span>
        </Link>
        <Link className="btn secondary" to="/patient/profile">
          <span>{t("nav.profile")}</span>
        </Link>
      </div>
    </div>
  );
}
