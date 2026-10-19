import { useEffect, useRef, useState } from "react";
import { useI18n } from "./i18n";

// Browser speech recognition only. Audio never leaves the browser through our code;
// we only ever send the text the patient confirms. Never auto-submits.
type SR = any;
function getSR(): SR | null {
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export function speechSupported() {
  return typeof window !== "undefined" && !!getSR();
}

export function MicButton({ onText, lang }: { onText: (text: string) => void; lang?: string }) {
  const { t, speechLang } = useI18n();
  const [listening, setListening] = useState(false);
  const recRef = useRef<SR | null>(null);
  useEffect(() => () => recRef.current?.abort?.(), []);
  if (!speechSupported()) return null; // hide when unsupported; typing always works
  const start = () => {
    const Ctor = getSR();
    const rec = new Ctor();
    rec.lang = lang ?? speechLang;
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.onresult = (e: any) => {
      const text = Array.from(e.results).map((r: any) => r[0].transcript).join(" ");
      onText(text);
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recRef.current = rec;
    setListening(true);
    rec.start();
  };
  const stop = () => recRef.current?.stop();
  return (
    <button type="button" className={`btn mic ${listening ? "listening" : ""}`} onClick={listening ? stop : start} aria-pressed={listening}>
      <span aria-hidden>🎤</span> {listening ? t("intake.mic_stop") : t("intake.mic")}
      {listening && <span className="sr-only">{t("intake.listening")}</span>}
    </button>
  );
}
