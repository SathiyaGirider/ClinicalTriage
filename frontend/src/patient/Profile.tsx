import { useState, type FormEvent } from "react";
import { put } from "../shared/api";
import { useAuth } from "../shared/auth";
import { LANGS, useI18n } from "../shared/i18n";
import { Button, Field, Select, Banner, ErrorBox } from "../shared/ui";

export default function Profile() {
  const { me, refresh } = useAuth();
  const { t, setLang } = useI18n();
  const [f, setF] = useState({
    full_name: me?.full_name ?? "",
    age: me?.age && /^\d+$/.test(me.age) ? me.age : "",
    language: (me?.language ?? "en") as "en" | "ta",
    area: me?.area ?? "",
    abha_address: me?.abha_address ?? "",
  });
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSaved(false);
    setBusy(true);
    try {
      await put("/me/profile", {
        full_name: f.full_name,
        age: f.age ? Number(f.age) : undefined,
        language: f.language,
        area: f.area,
        abha_address: f.abha_address ? f.abha_address.trim() : undefined,
      });
      setLang(f.language);
      await refresh();
      setSaved(true);
    } catch (ex) {
      setErr(ex);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 640, margin: "0 auto", padding: "1rem" }}>
      <form className="card" onSubmit={submit}>
        <h1 style={{ marginTop: 0, marginBottom: "1.25rem" }}>{t("prof.title")}</h1>

        <Banner
          variant="info"
          title="ABDM Simulation"
          style={{ marginBottom: "1.25rem" }}
        >
          LifeLine simulates Ayushman Bharat Digital Mission (ABDM) features for local demonstration.
          Never use real Aadhaar or actual ABHA credentials.
        </Banner>

        <Field label={t("auth.full_name")} required>
          <input
            value={f.full_name}
            onChange={(e) => setF({ ...f, full_name: e.target.value })}
            required
            disabled={busy}
          />
        </Field>

        <Field label={t("auth.age")}>
          <input
            type="number"
            min={0}
            max={125}
            value={f.age}
            onChange={(e) => setF({ ...f, age: e.target.value })}
            disabled={busy}
          />
        </Field>

        <Field label={t("common.language")}>
          <Select
            value={f.language}
            onChange={(e) => setF({ ...f, language: e.target.value as "en" | "ta" })}
            options={Object.entries(LANGS)
              .filter(([c]) => c === "en" || c === "ta")
              .map(([c, d]) => ({ value: c, label: d._meta.name }))}
            disabled={busy}
          />
        </Field>

        <Field label={t("auth.area")}>
          <input
            value={f.area}
            onChange={(e) => setF({ ...f, area: e.target.value })}
            disabled={busy}
          />
        </Field>

        <Field
          label="Synthetic ABHA Address (Simulation)"
          hint="Format: username@abdm or username@demo. Synthetic only."
        >
          <input
            placeholder="e.g. anitha.kumar@abdm"
            value={f.abha_address}
            onChange={(e) => setF({ ...f, abha_address: e.target.value })}
            disabled={busy}
          />
        </Field>

        <ErrorBox error={err} />
        {saved && <Banner variant="success" style={{ marginBottom: "1rem" }}>{t("prof.saved")}</Banner>}

        <Button type="submit" block disabled={busy} loading={busy}>
          {t("common.save")}
        </Button>
      </form>

      {/* Simulated ABHA Health ID Card for Scan & Share */}
      <div className="card" style={{ marginTop: "1.5rem" }}>
        <h2 style={{ fontSize: "1.1rem", marginTop: 0 }}>Simulated ABHA Digital Card</h2>
        <p className="small-text muted">
          Use this simulated digital badge at the hospital nurse check-in desk for express Scan &amp; Share registration.
        </p>
        <div
          style={{
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            padding: "1.25rem",
            background: "var(--surface)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "1rem",
          }}
        >
          <div>
            <div style={{ fontWeight: 600, fontSize: "1.05rem" }}>{me?.full_name || "Patient"}</div>
            <div className="small-text muted">Age: {me?.age || "—"} | Language: {me?.language?.toUpperCase() || "EN"}</div>
            <div style={{ fontFamily: "monospace", fontSize: "0.95rem", color: "var(--primary)", marginTop: "0.25rem" }}>
              {me?.abha_address || "no-abha@abdm"}
            </div>
            <span className="pill" style={{ marginTop: "0.5rem" }}>Synthetic ABHA · Simulation</span>
          </div>
          <div
            style={{
              padding: "0.75rem",
              background: "#ffffff",
              border: "1px dashed var(--border)",
              borderRadius: 4,
              textAlign: "center",
              minWidth: 120,
            }}
          >
            <div style={{ fontSize: "0.7rem", color: "#64748b", fontWeight: 700, letterSpacing: "0.05em", marginBottom: 4 }}>
              SCAN &amp; SHARE
            </div>
            <div
              style={{
                width: 72,
                height: 72,
                margin: "0 auto",
                background: "repeating-linear-gradient(45deg, #0f172a, #0f172a 4px, #ffffff 4px, #ffffff 8px)",
                borderRadius: 2,
              }}
              aria-label="Simulated QR Code"
            />
            <div style={{ fontSize: "0.65rem", color: "#94a3b8", marginTop: 4 }}>
              Code: {me?.id ? `PT-${me.id}` : "PT-0"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
