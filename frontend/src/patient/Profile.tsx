import { useState, type FormEvent } from "react";
import { put } from "../shared/api";
import { useAuth } from "../shared/auth";
import { LANGS, useI18n } from "../shared/i18n";
import { ErrorBox } from "../shared/ui";

export default function Profile() {
  const { me, refresh } = useAuth();
  const { t, setLang } = useI18n();
  const [f, setF] = useState({ full_name: me?.full_name ?? "", age: me?.age && /^\d+$/.test(me.age) ? me.age : "", language: me?.language ?? "en", area: me?.area ?? "" });
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSaved(false);
    try {
      await put("/me/profile", { full_name: f.full_name, age: f.age ? Number(f.age) : undefined, language: f.language, area: f.area });
      setLang(f.language);
      await refresh();
      setSaved(true);
    } catch (ex) { setErr(ex); }
  };
  return (
    <form className="card" onSubmit={submit}>
      <h1>{t("prof.title")}</h1>
      <label className="field">{t("auth.full_name")}<input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} required /></label>
      <label className="field">{t("auth.age")}<input type="number" min={0} max={125} value={f.age} onChange={(e) => setF({ ...f, age: e.target.value })} /></label>
      <label className="field">{t("common.language")}
        <select value={f.language} onChange={(e) => setF({ ...f, language: e.target.value as "en" | "ta" })}>
          {Object.entries(LANGS).filter(([c]) => c === "en" || c === "ta").map(([c, d]) => <option key={c} value={c}>{d._meta.name}</option>)}
        </select>
      </label>
      <label className="field">{t("auth.area")}<input value={f.area} onChange={(e) => setF({ ...f, area: e.target.value })} /></label>
      <ErrorBox error={err} />
      {saved && <p className="notice">{t("prof.saved")}</p>}
      <button className="btn block">{t("common.save")}</button>
    </form>
  );
}
