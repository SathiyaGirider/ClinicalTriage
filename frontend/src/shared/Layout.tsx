import { type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { useAuth } from "./auth";
import { LanguageSwitch, useI18n } from "./i18n";
import { DemoBanner, SafetyBanner } from "./ui";

export function Layout({ children, nav, wide = false }: { children: ReactNode; nav?: { to: string; label: string }[]; wide?: boolean }) {
  const { me, logout } = useAuth();
  const { t } = useI18n();
  return (
    <div className={`app ${wide ? "wide" : ""}`}>
      <DemoBanner />
      <SafetyBanner />
      <header className="topbar">
        <Link to="/" className="brand">
          <img src="/icon.svg" alt="" width={28} height={28} /> {t("app.name")}
        </Link>
        <div className="topbar-right">
          {me?.role === "patient" && <LanguageSwitch />}
          {me && (
            <button className="btn small ghost" onClick={logout}>
              {t("common.logout")}
            </button>
          )}
        </div>
      </header>
      {nav && (
        <nav className="tabs">
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to} end className={({ isActive }) => (isActive ? "active" : "")}>
              {n.label}
            </NavLink>
          ))}
        </nav>
      )}
      <main>{children}</main>
    </div>
  );
}
