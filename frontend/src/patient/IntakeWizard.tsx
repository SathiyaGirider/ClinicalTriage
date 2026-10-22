import { useEffect, useState } from "react";
import { api, ApiError, post } from "../shared/api";
import { useI18n } from "../shared/i18n";
import { CheckIcon } from "../shared/icons";
import { ErrorBox, Loading } from "../shared/ui";
import { MicButton } from "../shared/voice";

export type Question = { key: string; kind: "text" | "adaptive" | "chips" | "multi" | "number"; question: string; options: string[]; source: string };
export type SessionView = {
  session_id: string; mode: string; language: string; done: boolean; current: Question | null; question_number: number;
  max_questions: number; age_prefilled: number | null; ended_early_for_safety: boolean;
};

const FIXED = new Set(["complaint", "safety_screen", "duration", "age", "conditions", "change", "change_when"]);
const SYMPTOM_CHIPS = ["fever", "cough", "cold", "headache", "stomach", "rash", "joint", "ear"];

export function QuestionInput({ q, initial, onSubmit, busy, staff = false }: {
  q: Question; initial?: any; onSubmit: (v: any) => void; busy: boolean; staff?: boolean;
}) {
  const { t } = useI18n();
  const [text, setText] = useState<string>(typeof initial === "string" ? initial : initial != null && q.kind === "number" ? String(initial) : "");
  const [multi, setMulti] = useState<string[]>(Array.isArray(initial) ? initial : []);
  const [heard, setHeard] = useState(false);
  useEffect(() => {
    setText(typeof initial === "string" ? initial : initial != null && q.kind === "number" ? String(initial) : "");
    setMulti(Array.isArray(initial) ? initial : []);
    setHeard(false);
  }, [q.key]); // eslint-disable-line react-hooks/exhaustive-deps
  const label = FIXED.has(q.key) ? t(`q.${q.key}`) : q.question;
  const chipLabel = (o: string) => t(`chip.${o}`);

  if (q.kind === "multi") {
    const isScreen = q.key === "safety_screen";
    const toggle = (o: string) => {
      if (o === "none") return setMulti(["none"]);
      setMulti((m) => (m.includes(o) ? m.filter((x) => x !== o) : [...m.filter((x) => x !== "none"), o]));
    };
    return (
      <fieldset className="card" style={{ border: "none" }}>
        <legend><h2>{label}</h2></legend>
        {q.options.includes("none") && (
          <button type="button" className={`chip none-big ${multi.includes("none") ? "on" : ""}`} onClick={() => (isScreen ? onSubmit(["none"]) : toggle("none"))} disabled={busy}>
            <CheckIcon width={18} height={18} />
            <span>{t("intake.none_of_these")}</span>
          </button>
        )}
        <div className="chips">
          {q.options.filter((o) => o !== "none").map((o) => (
            <button type="button" key={o} className={`chip ${multi.includes(o) ? "on" : ""}`} aria-pressed={multi.includes(o)} onClick={() => toggle(o)}>
              {chipLabel(o)}
            </button>
          ))}
        </div>
        <button className="btn block" disabled={busy || multi.length === 0} onClick={() => onSubmit(multi)}>{t("common.next")}</button>
      </fieldset>
    );
  }
  if (q.kind === "chips") {
    return (
      <div className="card">
        <h2>{label}</h2>
        <div className="chips">
          {q.options.map((o) => (
            <button type="button" key={o} className={`chip ${initial === o ? "on" : ""}`} onClick={() => onSubmit(o)} disabled={busy}>{chipLabel(o)}</button>
          ))}
        </div>
      </div>
    );
  }
  if (q.kind === "number") {
    return (
      <form className="card" onSubmit={(e) => { e.preventDefault(); onSubmit(text); }}>
        <h2>{label}</h2>
        <input type="number" inputMode="numeric" min={0} max={125} value={text} onChange={(e) => setText(e.target.value)} required aria-label={label} />
        <button className="btn block" style={{ marginTop: "0.6rem" }} disabled={busy || !text}>{t("common.next")}</button>
      </form>
    );
  }
  return (
    <form className="card" onSubmit={(e) => { e.preventDefault(); onSubmit(text.trim()); }}>
      <h2>{label}</h2>
      {q.key === "complaint" && !staff && (
        <div>
          <span className="muted small-text">{t("chips.symptom_examples")}</span>
          <div className="chips">
            {SYMPTOM_CHIPS.map((s) => (
              <button type="button" className="chip" key={s} onClick={() => setText((x) => (x ? `${x}, ${t(`sym.${s}`)}` : t(`sym.${s}`)))}>{t(`sym.${s}`)}</button>
            ))}
          </div>
        </div>
      )}
      <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={t("intake.type_or_speak")} aria-label={label} maxLength={2000} />
      {heard && <p className="notice">{t("intake.check_text")}</p>}
      <div className="row" style={{ marginTop: "0.6rem" }}>
        <MicButton onText={(s) => { setText((x) => (x ? `${x} ${s}` : s)); setHeard(true); }} />
        <button className="btn" style={{ flex: 1 }} disabled={busy || (["complaint", "change"].includes(q.key) && !text.trim())}>{t("common.next")}</button>
      </div>
    </form>
  );
}

type Understood = { your_words: string; answers: { key: string; question: string; kind: Question["kind"]; options: string[]; answer: any }[] };

export function ConfirmScreen({ sessionId, onConfirm, busy }: { sessionId: string; onConfirm: () => void; busy: boolean }) {
  const { t } = useI18n();
  const [data, setData] = useState<Understood | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const load = () => api(`/intake/session/${sessionId}/result`).then((r) => setData(r.understood)).catch(setErr);
  useEffect(() => { load(); }, [sessionId]); // eslint-disable-line react-hooks/exhaustive-deps
  if (err) return <ErrorBox error={err} onRetry={() => { setErr(null); load(); }} />;
  if (!data) return <Loading />;
  const show = (a: Understood["answers"][number]) =>
    Array.isArray(a.answer) ? a.answer.map((x: string) => t(`chip.${x}`)).join(", ") : a.kind === "chips" ? t(`chip.${a.answer}`) : String(a.answer ?? "");
  return (
    <div>
      <h1>{t("intake.confirm_title")}</h1>
      <p className="muted">{t("intake.confirm_sub")}</p>
      {data.answers.map((a) =>
        editing === a.key ? (
          <QuestionInput key={a.key} q={{ ...a, source: "" }} initial={a.answer} busy={busy}
            onSubmit={async (v) => { try { await post(`/intake/session/${sessionId}/answer`, { key: a.key, answer: v }); setEditing(null); load(); } catch (e) { setErr(e); } }} />
        ) : (
          <div className="card spread" key={a.key}>
            <div>
              <div className="muted small-text">{FIXED.has(a.key) ? t(`q.${a.key}`) : a.question}</div>
              <div>{show(a)}</div>
            </div>
            <button className="btn small secondary" onClick={() => setEditing(a.key)}>{t("intake.edit")}</button>
          </div>
        ),
      )}
      <button className="btn block" onClick={onConfirm} disabled={busy || !!editing}>{t("intake.looks_right")}</button>
    </div>
  );
}

export default function IntakeWizard({ start, onFinished, confirm = true, staff = false }: {
  start: () => Promise<SessionView>; onFinished: (sessionId: string, endedEarly: boolean) => void; confirm?: boolean; staff?: boolean;
}) {
  const { t } = useI18n();
  const [view, setView] = useState<SessionView | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [pending, setPending] = useState<any>(undefined);
  useEffect(() => { start().then(setView).catch(setErr); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const send = async (v: any) => {
    if (!view?.current) return;
    setBusy(true);
    setErr(null);
    setPending(v);
    try {
      const next = await post<SessionView>(`/intake/session/${view.session_id}/answer`, { key: view.current.key, answer: v });
      setPending(undefined);
      setView(next);
      if (next.done && (!confirm || next.ended_early_for_safety)) onFinished(next.session_id, next.ended_early_for_safety);
    } catch (e) {
      setErr(e); // answer stays in `pending` so the patient does not retype it
    } finally {
      setBusy(false);
    }
  };
  // Local draft retention
  useEffect(() => {
    if (view && pending !== undefined) {
      try {
        localStorage.setItem(`lifeline_draft_${view.session_id}`, JSON.stringify({ key: view.current?.key, val: pending }));
      } catch {}
    }
  }, [view, pending]);

  if (!view) return err ? <ErrorBox error={err} onRetry={() => { setErr(null); start().then(setView).catch(setErr); }} /> : <Loading />;
  if (view.done) {
    if (!confirm || view.ended_early_for_safety) return <Loading />;
    return <ConfirmScreen sessionId={view.session_id} busy={busy} onConfirm={() => onFinished(view.session_id, false)} />;
  }

  const isOffline = (err instanceof ApiError && err.offline) || (typeof navigator !== "undefined" && !navigator.onLine);

  return (
    <div>
      <div className="spread" style={{ alignItems: "center", marginBottom: "0.5rem" }}>
        <p className="muted" style={{ margin: 0 }}>
          {t("intake.progress", { n: view.question_number, max: view.max_questions })}
        </p>
      </div>

      {isOffline && (
        <div className="notice" style={{ marginBottom: "1rem", borderColor: "var(--status-urgent-solid)" }}>
          <strong>Offline:</strong> No network. Your answers are kept. Try again.
        </div>
      )}

      {view.age_prefilled != null && view.question_number === 1 && (
        <p className="muted small-text">{t("intake.age_prefilled", { age: view.age_prefilled })}</p>
      )}

      {view.current && (
        <QuestionInput
          q={view.current}
          initial={pending}
          onSubmit={send}
          busy={busy}
          staff={staff}
        />
      )}

      <ErrorBox
        error={err}
        onRetry={pending !== undefined ? () => send(pending) : undefined}
      />
    </div>
  );
}
