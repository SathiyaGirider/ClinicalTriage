import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../shared/auth";
import { LANGS, LanguageSwitch, useI18n } from "../shared/i18n";
import { Layout } from "../shared/Layout";
import { Button, ErrorBox } from "../shared/ui";

export default function Register() {
  const { register } = useAuth();
  const { t, lang, setLang } = useI18n();
  const nav = useNavigate();
  const [f, setF] = useState({ full_name: "", email: "", password: "", age: "", dob: "", area: "" });
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      await register({
        full_name: f.full_name, email: f.email.trim(), password: f.password, language: lang in LANGS && (lang === "ta" || lang === "en") ? lang : "en",
        age: f.age ? Number(f.age) : undefined, dob: f.dob || undefined, area: f.area || undefined,
      });
      setLang(lang);
      nav("/patient", { replace: true });
    } catch (ex) {
      setErr(ex);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Layout>
      <div className="auth-wrapper">
        <div className="auth-box">
          <div className="auth-header">
            <div>
              <h1>{t("auth.register")}</h1>
              <p className="auth-subtitle">Create a patient account for hospital OPD</p>
            </div>
            <LanguageSwitch />
          </div>
          <form onSubmit={submit}>
            <label className="field">{t("auth.full_name")}<input value={f.full_name} onChange={set("full_name")} required maxLength={120} placeholder="Full Name" /></label>
            <label className="field">{t("auth.email")}<input type="email" value={f.email} onChange={set("email")} required placeholder="name@example.com" /></label>
            <label className="field">
              {t("auth.password")} <span className="muted small-text">({t("auth.password_hint")})</span>
              <input type="password" value={f.password} onChange={set("password")} minLength={10} required autoComplete="new-password" />
            </label>
            <div className="row">
              <label className="field" style={{ flex: 1 }}>{t("auth.age")}<input type="number" min={0} max={125} value={f.age} onChange={set("age")} placeholder="e.g. 28" /></label>
              <label className="field" style={{ flex: 1 }}>{t("auth.dob")}<input type="date" value={f.dob} onChange={set("dob")} /></label>
            </div>
            <label className="field">{t("auth.area")}<input value={f.area} onChange={set("area")} maxLength={80} placeholder="e.g. Adyar, Chennai" /></label>
            <p className="muted small-text" style={{ marginBottom: "1rem" }}>{t("auth.no_phone")}</p>
            <ErrorBox error={err} />
            <Button className="block" busy={busy} disabled={!f.age && !f.dob}>{t("auth.register")}</Button>
          </form>
          <p style={{ marginTop: "1rem", textAlign: "center", fontSize: "0.9rem" }}><Link to="/login">{t("auth.have_account")}</Link></p>
        </div>
      </div>
    </Layout>
  );
}

