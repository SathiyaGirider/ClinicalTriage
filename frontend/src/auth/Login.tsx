import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { homeFor, useAuth } from "../shared/auth";
import { LanguageSwitch, useI18n } from "../shared/i18n";
import { Layout } from "../shared/Layout";
import { Banner, Button, ErrorBox } from "../shared/ui";

export default function Login() {
  const { login } = useAuth();
  const { t, setLang } = useI18n();
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const returnTo = sp.get("return_to");
  const isExpired = sp.get("expired") === "1";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const me = await login(email.trim(), password);
      if (me.role === "patient" && me.language) setLang(me.language);
      if (me.role !== "patient") setLang("en");

      const defaultHome = homeFor(me.role);
      if (returnTo && decodeURIComponent(returnTo).startsWith(defaultHome)) {
        nav(decodeURIComponent(returnTo), { replace: true });
      } else {
        nav(defaultHome, { replace: true });
      }
    } catch (ex) {
      setErr(ex);
    } finally {
      setBusy(false);
    }
  };

  const fillDemo = (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword("Password123!");
  };

  return (
    <Layout>
      <div className="auth-wrapper">
        <div className="auth-box">
          <div className="auth-header">
            <div>
              <h1>{t("auth.login")}</h1>
              <p className="auth-subtitle">Sign in to your clinical OPD portal</p>
            </div>
            <LanguageSwitch />
          </div>

          {isExpired && (
            <Banner variant="warn" className="mb-2">
              Your session expired. Please log in again to continue your work safely.
            </Banner>
          )}

          <form onSubmit={submit}>
            <label className="field">
              {t("auth.email")}
              <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="name@example.com" />
            </label>
            <label className="field">
              {t("auth.password")}
              <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </label>
            <ErrorBox error={err} />
            <Button className="block" busy={busy} style={{ marginTop: "0.5rem" }}>
              {t("auth.login")}
            </Button>
          </form>

          <p style={{ marginTop: "1rem", textAlign: "center", fontSize: "0.9rem" }}>
            <Link to="/register">{t("auth.no_account")}</Link>
          </p>

          <div className="demo-account-pills">
            <div className="demo-account-label">
              <span>Demo Accounts (1-click fill)</span>
              <span className="muted" style={{ fontWeight: "normal", fontSize: "0.75rem" }}>Pass: Password123!</span>
            </div>
            <div className="demo-buttons-row">
              <button type="button" className="demo-btn" onClick={() => fillDemo("dr.gm.adyar@example.com")}>
                Doctor (Adyar)
              </button>
              <button type="button" className="demo-btn" onClick={() => fillDemo("nurse.adyar@example.com")}>
                Nurse (Adyar)
              </button>
              <button type="button" className="demo-btn" onClick={() => fillDemo("asha@example.com")}>
                Patient (Asha)
              </button>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}

