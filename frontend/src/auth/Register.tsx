import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../shared/auth";
import { LANGS, LanguageSwitch, useI18n } from "../shared/i18n";
import { Layout } from "../shared/Layout";
import { ErrorBox } from "../shared/ui";

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
      <div className="spread">
        <h1>{t("auth.register")}</h1>
        <LanguageSwitch />
      </div>
      <form onSubmit={submit} className="card">
        <label className="field">{t("auth.full_name")}<input value={f.full_name} onChange={set("full_name")} required maxLength={120} /></label>
        <label className="field">{t("auth.email")}<input type="email" value={f.email} onChange={set("email")} required /></label>
        <label className="field">
          {t("auth.password")} <span className="muted small-text">({t("auth.password_hint")})</span>
          <input type="password" value={f.password} onChange={set("password")} minLength={10} required autoComplete="new-password" />
        </label>
        <div className="row">
          <label className="field" style={{ flex: 1 }}>{t("auth.age")}<input type="number" min={0} max={125} value={f.age} onChange={set("age")} /></label>
          <label className="field" style={{ flex: 1 }}>{t("auth.dob")}<input type="date" value={f.dob} onChange={set("dob")} /></label>
        </div>
        <label className="field">{t("auth.area")}<input value={f.area} onChange={set("area")} maxLength={80} /></label>
        <p className="muted small-text">{t("auth.no_phone")}</p>
        <ErrorBox error={err} />
        <button className="btn block" disabled={busy || (!f.age && !f.dob)}>{t("auth.register")}</button>
      </form>
      <p><Link to="/login">{t("auth.have_account")}</Link></p>
    </Layout>
  );
}
