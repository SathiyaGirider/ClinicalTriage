import { useState, type FormEvent } from "react";
import { put } from "../shared/api";
import { useAuth } from "../shared/auth";
import { LANGS, useI18n } from "../shared/i18n";
import { Banner, Button, Card, ErrorBox, Field, Select } from "../shared/ui";

function getInitialDob(dobOrAge?: string | null): string {
  if (!dobOrAge) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(dobOrAge)) return dobOrAge;
  return "";
}

function calculateAge(dobStr: string): number | null {
  if (!dobStr) return null;
  const birth = new Date(dobStr);
  if (isNaN(birth.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const m = today.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) {
    age--;
  }
  return age >= 0 ? age : null;
}

export default function Profile() {
  const { me, refresh } = useAuth();
  const { t, setLang } = useI18n();

  const [f, setF] = useState({
    full_name: me?.full_name ?? "",
    dob: getInitialDob(me?.age),
    language: (me?.language ?? "en") as "en" | "ta",
    area: me?.area ?? "",
    abha_address: me?.abha_address ?? "",
  });

  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  // Derive age automatically from DOB in logic
  const calculatedAge = calculateAge(f.dob);
  const displayAge = calculatedAge !== null ? `${calculatedAge} years` : me?.age ? `${me.age} years` : "—";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSaved(false);
    setBusy(true);
    setErr(null);
    try {
      const derivedAge = calculatedAge ?? (me?.age && /^\d+$/.test(me.age) ? Number(me.age) : undefined);
      await put("/me/profile", {
        full_name: f.full_name.trim(),
        dob: f.dob || undefined,
        age: derivedAge,
        language: f.language,
        area: f.area ? f.area.trim() : undefined,
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
    <div style={{ maxWidth: 680, margin: "0 auto", padding: "1rem 0" }}>
      <div className="card">
        <h1 style={{ marginTop: 0, marginBottom: "0.5rem" }}>{t("prof.title")}</h1>
        <p className="muted small-text" style={{ marginBottom: "1.25rem" }}>
          Update your patient registration details and simulated ABDM credentials.
        </p>

        <Banner variant="info" className="mb-2">
          <strong>ABDM Simulation:</strong> LifeLine simulates Ayushman Bharat Digital Mission (ABDM) features for local academic demonstration. Never enter real Aadhaar or government health identifiers.
        </Banner>

        <form onSubmit={submit}>
          <Field label={t("auth.full_name")} required>
            <input
              type="text"
              value={f.full_name}
              onChange={(e) => setF({ ...f, full_name: e.target.value })}
              required
              disabled={busy}
              placeholder="Your full legal name"
            />
          </Field>

          {/* Date of Birth input: age is computed dynamically from this value */}
          <Field
            label="Date of Birth (DOB)"
            hint={
              calculatedAge !== null
                ? `Current calculated age: ${calculatedAge} years old (derived automatically from your date of birth)`
                : "Select your date of birth to automatically calculate your clinical age"
            }
            required
          >
            <input
              type="date"
              value={f.dob}
              onChange={(e) => setF({ ...f, dob: e.target.value })}
              max={new Date().toISOString().split("T")[0]}
              required
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

          <Field label={t("auth.area")} hint="Used to display nearest hospital distances">
            <input
              type="text"
              value={f.area}
              onChange={(e) => setF({ ...f, area: e.target.value })}
              disabled={busy}
              placeholder="e.g. Adyar, Chennai"
            />
          </Field>

          <Field
            label="Synthetic ABHA Address (Simulation)"
            hint="Simulated ABDM handle format: username@abdm or username@demo"
          >
            <input
              type="text"
              placeholder="e.g. asha@abdm"
              value={f.abha_address}
              onChange={(e) => setF({ ...f, abha_address: e.target.value })}
              disabled={busy}
            />
          </Field>

          <ErrorBox error={err} />
          {saved && (
            <Banner variant="routine" className="mb-2">
              {t("prof.saved")}
            </Banner>
          )}

          <Button type="submit" className="block" busy={busy} style={{ marginTop: "1rem" }}>
            {t("common.save")}
          </Button>
        </form>
      </div>

      {/* Simulated ABHA Digital Health Card & Real-World Use Case */}
      <div className="card" style={{ marginTop: "1.5rem" }}>
        <div className="spread" style={{ marginBottom: "0.5rem" }}>
          <h2 style={{ fontSize: "1.2rem", margin: 0 }}>Simulated ABHA Digital Health Card</h2>
          <span className="pill" style={{ background: "#e0f2fe", color: "#0369a1", fontWeight: 600 }}>
            ABDM Simulation
          </span>
        </div>

        {/* Clear clinical use case explanation */}
        <div
          style={{
            background: "var(--surface-muted)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "0.85rem 1rem",
            marginBottom: "1.25rem",
            fontSize: "0.88rem",
            lineHeight: 1.5,
          }}
        >
          <strong style={{ color: "var(--ink-primary)", display: "block", marginBottom: "0.25rem" }}>
            Real-World Clinical Use Case: Express OPD "Scan &amp; Share" Check-in
          </strong>
          <span className="muted">
            In modern Indian hospitals, patients do not fill manual paper slips. Instead, they present this QR code
            at the registration desk. The triage nurse scans the code via their terminal (
            <code>Nurse Dashboard &gt; Scan &amp; Share</code>
            ) to instantly pull verified demographic details (Name, Age/DOB, and Area) and issue an OPD token within
            seconds.
          </span>
        </div>

        {/* Digital ID Card Display */}
        <div
          style={{
            border: "1px solid var(--border-strong)",
            borderRadius: 12,
            background: "linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)",
            padding: "1.25rem",
            boxShadow: "0 2px 6px rgba(0,0,0,0.04)",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              borderBottom: "1px solid var(--border-subtle)",
              paddingBottom: "0.75rem",
              marginBottom: "1rem",
            }}
          >
            <div>
              <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--primary)", letterSpacing: "0.06em" }}>
                NATIONAL HEALTH AUTHORITY (SIMULATION)
              </div>
              <div style={{ fontSize: "0.7rem", color: "var(--ink-muted)" }}>Ayushman Bharat Health Account (ABHA)</div>
            </div>
            <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#166534", background: "#dcfce7", padding: "2px 8px", borderRadius: 4 }}>
              Active
            </div>
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "1.25rem",
            }}
          >
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--ink-primary)" }}>
                {f.full_name || me?.full_name || "Patient"}
              </div>
              <div style={{ fontSize: "0.88rem", color: "var(--ink-secondary)", marginTop: "0.25rem" }}>
                <strong>DOB:</strong> {f.dob || "Not specified"} ({displayAge})
              </div>
              <div style={{ fontSize: "0.88rem", color: "var(--ink-secondary)", marginTop: "0.2rem" }}>
                <strong>Area:</strong> {f.area || me?.area || "Chennai"}
              </div>
              <div
                style={{
                  fontFamily: "monospace",
                  fontSize: "0.95rem",
                  fontWeight: 600,
                  color: "var(--primary)",
                  marginTop: "0.5rem",
                  padding: "4px 8px",
                  background: "#ffffff",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: 6,
                  display: "inline-block",
                }}
              >
                {f.abha_address || me?.abha_address || `${(me?.email || "patient").split("@")[0]}@abdm`}
              </div>
            </div>

            {/* QR Scanner Target */}
            <div
              style={{
                padding: "0.85rem",
                background: "#ffffff",
                border: "1px solid var(--border-strong)",
                borderRadius: 8,
                textAlign: "center",
                boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
              }}
            >
              <div style={{ fontSize: "0.7rem", color: "var(--ink-secondary)", fontWeight: 700, letterSpacing: "0.06em", marginBottom: 6 }}>
                SCAN &amp; SHARE
              </div>
              <div
                style={{
                  width: 80,
                  height: 80,
                  margin: "0 auto",
                  background: "repeating-linear-gradient(45deg, #0f172a, #0f172a 5px, #ffffff 5px, #ffffff 10px)",
                  borderRadius: 4,
                  border: "1px solid #cbd5e1",
                }}
                aria-label="Patient ABHA QR Code"
              />
              <div style={{ fontSize: "0.7rem", fontWeight: 600, color: "var(--primary)", marginTop: 6 }}>
                ID: {me?.id ? `PT-${me.id}` : "PT-0"}
              </div>
              <div style={{ fontSize: "0.62rem", color: "var(--ink-muted)" }}>Scan at Nurse Desk</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
