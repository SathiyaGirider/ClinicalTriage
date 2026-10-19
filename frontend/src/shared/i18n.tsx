import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

// Every JSON file in ./i18n is a language. Adding a language = adding one file.
const files = import.meta.glob("./i18n/*.json", { eager: true }) as Record<string, { default: Record<string, any> }>;
export const LANGS: Record<string, Record<string, any>> = {};
for (const [path, mod] of Object.entries(files)) {
  const code = path.split("/").pop()!.replace(".json", "");
  LANGS[code] = (mod as any).default ?? mod;
}

const KEY = "lifeline.lang";
type Ctx = { lang: string; setLang: (l: string) => void; t: (k: string, vars?: Record<string, string | number>) => string; speechLang: string };
const I18nCtx = createContext<Ctx | null>(null);

export function translate(lang: string, k: string, vars?: Record<string, string | number>) {
  let s: string = LANGS[lang]?.[k] ?? LANGS.en?.[k] ?? k;
  if (vars) for (const [name, v] of Object.entries(vars)) s = s.split(`{${name}}`).join(String(v));
  return s;
}

export function I18nProvider({ children, initial }: { children: ReactNode; initial?: string }) {
  const [lang, setLangState] = useState<string>(() => {
    try {
      return localStorage.getItem(KEY) || initial || "en";
    } catch {
      return initial || "en";
    }
  });
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const setLang = (l: string) => {
    setLangState(l);
    try {
      localStorage.setItem(KEY, l);
    } catch {
      /* ignore */
    }
  };
  const t = (k: string, vars?: Record<string, string | number>) => translate(lang, k, vars);
  return <I18nCtx.Provider value={{ lang, setLang, t, speechLang: LANGS[lang]?._meta?.speech ?? "en-IN" }}>{children}</I18nCtx.Provider>;
}

export function useI18n() {
  const c = useContext(I18nCtx);
  if (!c) throw new Error("useI18n outside I18nProvider");
  return c;
}

export function LanguageSwitch() {
  const { lang, setLang, t } = useI18n();
  return (
    <label className="lang-switch">
      <span className="sr-only">{t("common.language")}</span>
      <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label={t("common.language")}>
        {Object.entries(LANGS).map(([code, d]) => (
          <option key={code} value={code}>
            {d._meta?.name ?? code}
          </option>
        ))}
      </select>
    </label>
  );
}
