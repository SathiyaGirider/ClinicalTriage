import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { homeFor, useAuth } from "../shared/auth";
import { LanguageSwitch, useI18n } from "../shared/i18n";
import { Layout } from "../shared/Layout";
import { ErrorBox } from "../shared/ui";

export default function Login() {
  const { login } = useAuth();
  const { t, setLang } = useI18n();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const me = await login(email.trim(), password);
      if (me.role === "patient" && me.language) setLang(me.language);
      if (me.role !== "patient") setLang("en");
      nav(homeFor(me.role), { replace: true });
    } catch (ex) {
      setErr(ex);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Layout>
      <div className="spread">
        <h1>{t("auth.login")}</h1>
        <LanguageSwitch />
      </div>
      <form onSubmit={submit} className="card">
        <label className="field">
          {t("auth.email")}
          <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label className="field">
          {t("auth.password")}
          <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        <ErrorBox error={err} />
        <button className="btn block" disabled={busy}>
          {t("auth.login")}
        </button>
      </form>
      <p>
        <Link to="/register">{t("auth.no_account")}</Link>
      </p>
    </Layout>
  );
}
