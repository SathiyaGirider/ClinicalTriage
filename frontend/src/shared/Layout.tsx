import { type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { useAuth } from "./auth";
import { LanguageSwitch, useI18n } from "./i18n";

export function Layout({ children, nav, wide = false }: { children: ReactNode; nav?: { to: string; label: string }[]; wide?: boolean }) {
  const { me, logout } = useAuth();
  const { t } = useI18n();
  return (
    <div className={`app ${wide ? "wide" : ""}`}>
      <header className="topbar-wrapper">
        <div className="topbar">
          <Link to="/" className="brand">
            <img src="/icon.svg" alt="" width={26} height={26} />
            <span>{t("app.name")}</span>
            <span className="brand-badge">OPD System</span>
          </Link>
          {me && (
            <div className="topbar-user">
              {me.hospital_name && <span className="hospital-tag">{me.hospital_name}</span>}
              <strong>{me.full_name}</strong>
              <span className={`user-badge ${me.role}`}>{me.role}</span>
            </div>
          )}
          <div className="topbar-right">
            {me?.role === "patient" && <LanguageSwitch />}
            {me && (
              <button className="btn small ghost" onClick={logout}>
                {t("common.logout")}
              </button>
            )}
          </div>
        </div>
      </header>
      {nav && (
        <nav className="tabs-wrapper">
          <div className="tabs">
            {nav.map((n) => (
              <NavLink key={n.to} to={n.to} end className={({ isActive }) => (isActive ? "active" : "")}>
                {n.label}
              </NavLink>
            ))}
          </div>
        </nav>
      )}
      <main>{children}</main>
    </div>
  );
}
