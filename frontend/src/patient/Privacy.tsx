import { useEffect, useState } from "react";
import { api, fmtDate, post } from "../shared/api";
import { useAuth } from "../shared/auth";
import { useI18n } from "../shared/i18n";
import { Banner, Button, Card, Dialog, EmptyState, ErrorBox, Loading, StatusPill } from "../shared/ui";

type ConsentItem = {
  id: number;
  doctor_name: string;
  specialty: string;
  hospital_name: string;
  purpose: string;
  hi_types: string[];
  date_from: string;
  date_to: string;
  status: string;
  expires_at: string | null;
  created_at: string;
};

type InboxResp = {
  disclaimer: string;
  abha_address: string | null;
  pending: ConsentItem[];
  active: ConsentItem[];
  past: ConsentItem[];
};

export default function Privacy() {
  const { t, lang } = useI18n();
  const { me } = useAuth();
  const [data, setData] = useState<InboxResp | null>(null);
  const [log, setLog] = useState<{ viewer: string; hospital: string; what: string; ts: string }[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  // Approval modal state
  const [approvingReq, setApprovingReq] = useState<ConsentItem | null>(null);
  const [durationHours, setDurationHours] = useState<24 | 168 | 720>(24);
  const [selectedHiTypes, setSelectedHiTypes] = useState<string[]>(["OPConsultNote", "Prescription"]);

  // Revoke modal state
  const [revokingReq, setRevokingReq] = useState<ConsentItem | null>(null);

  const load = () => {
    Promise.all([
      api<InboxResp>("/abdm/consent/patient/inbox"),
      api<any[]>("/me/access-log"),
    ])
      .then(([inbox, accessLog]) => {
        setData(inbox);
        setLog(accessLog);
      })
      .catch(setErr);
  };

  useEffect(() => {
    load();
  }, []);

  const handleApprove = async () => {
    if (!approvingReq) return;
    setBusy(true);
    try {
      await post(`/abdm/consent/${approvingReq.id}/approve`, {
        duration_hours: durationHours,
        hi_types: selectedHiTypes,
      });
      setApprovingReq(null);
      load();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };

  const handleDeny = async (reqId: number) => {
    setBusy(true);
    try {
      await post(`/abdm/consent/${reqId}/deny`, { reason: "Denied by patient" });
      load();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };

  const handleRevoke = async () => {
    if (!revokingReq) return;
    setBusy(true);
    try {
      await post(`/abdm/consent/${revokingReq.id}/revoke`, { reason: "Revoked by patient" });
      setRevokingReq(null);
      load();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="spread" style={{ marginBottom: "0.5rem" }}>
        <h1>{t("priv.title")}</h1>
      </div>

      <Banner variant="info" className="mb-2">
        <strong>ABDM simulation. Not connected to ABDM.</strong> Health records are accessed only via time-bound consent requests you explicitly approve.
      </Banner>

      <Card className="mb-2">
        <div className="spread">
          <div>
            <div className="muted small-text">Synthetic ABHA Address</div>
            <strong style={{ fontSize: "1.1rem" }}>{data?.abha_address || `${me?.email.split("@")[0]}@abdm`}</strong>
          </div>
          <StatusPill variant="neutral" label="Simulated ID" />
        </div>
        <p className="muted small-text" style={{ margin: "0.5rem 0 0" }}>
          This synthetic identifier simulates the Ayushman Bharat Digital Mission (ABDM) address used for OPD routing and consent management.
        </p>
      </Card>

      <ErrorBox error={err} />

      {!data ? (
        <Loading />
      ) : (
        <>
          {/* Section 1: Pending Access Requests */}
          <section style={{ marginTop: "1.5rem" }}>
            <h2>Access Requests Inbox ({data.pending.length})</h2>
            <p className="muted small-text">
              Doctors outside your primary clinic must request temporary permission to view your prior health records.
            </p>

            {data.pending.length === 0 ? (
              <EmptyState title="No pending requests" description="No doctor is currently requesting access to your outside records." />
            ) : (
              data.pending.map((req) => (
                <Card key={req.id} className="mb-2">
                  <div className="spread">
                    <div>
                      <strong>{req.doctor_name}</strong> · {req.specialty}
                      <div className="muted small-text">{req.hospital_name}</div>
                    </div>
                    <StatusPill variant="urgent" label="Pending Approval" />
                  </div>
                  <div style={{ margin: "0.75rem 0" }}>
                    <div className="small-text"><strong>Purpose:</strong> {req.purpose}</div>
                    <div className="small-text"><strong>Record types:</strong> {req.hi_types.join(", ")}</div>
                    <div className="small-text"><strong>Period:</strong> {req.date_from} to {req.date_to}</div>
                  </div>
                  <div className="row" style={{ gap: "0.5rem" }}>
                    <Button
                      variant="primary"
                      size="small"
                      onClick={() => {
                        setApprovingReq(req);
                        setSelectedHiTypes(req.hi_types);
                      }}
                    >
                      Approve access
                    </Button>
                    <Button
                      variant="outline"
                      size="small"
                      disabled={busy}
                      onClick={() => handleDeny(req.id)}
                    >
                      Deny
                    </Button>
                  </div>
                </Card>
              ))
            )}
          </section>

          {/* Section 2: Active Consents */}
          <section style={{ marginTop: "2rem" }}>
            <h2>Active Permissions ({data.active.length})</h2>
            <p className="muted small-text">
              Health information is shared with these doctors only until the expiry time or until you revoke permission.
            </p>

            {data.active.length === 0 ? (
              <EmptyState title="No active permissions" description="You have not granted access to any outside doctors." />
            ) : (
              data.active.map((req) => (
                <Card key={req.id} className="mb-2 ok">
                  <div className="spread">
                    <div>
                      <strong>{req.doctor_name}</strong> · {req.specialty}
                      <div className="muted small-text">{req.hospital_name}</div>
                    </div>
                    <StatusPill variant="routine" label="Active Permission" />
                  </div>
                  <div style={{ margin: "0.5rem 0" }} className="small-text">
                    <div><strong>Types:</strong> {req.hi_types.join(", ")}</div>
                    <div><strong>Expires:</strong> {req.expires_at ? `${fmtDate(req.expires_at, lang)} ${new Date(req.expires_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}` : "—"}</div>
                  </div>
                  <Button
                    variant="warn"
                    size="small"
                    onClick={() => setRevokingReq(req)}
                  >
                    Revoke access
                  </Button>
                </Card>
              ))
            )}
          </section>

          {/* Section 3: Past Consents */}
          {data.past.length > 0 && (
            <section style={{ marginTop: "2rem" }}>
              <details>
                <summary style={{ cursor: "pointer", fontWeight: 600 }}>Past Consents History ({data.past.length})</summary>
                <div style={{ marginTop: "0.75rem" }}>
                  {data.past.map((req) => (
                    <Card key={req.id} className="mb-2">
                      <div className="spread">
                        <div>
                          <strong>{req.doctor_name}</strong> · {req.hospital_name}
                          <div className="muted small-text">{req.purpose} · {req.status}</div>
                        </div>
                        <StatusPill variant={req.status === "DENIED" ? "urgent" : "neutral"} label={req.status} />
                      </div>
                    </Card>
                  ))}
                </div>
              </details>
            </section>
          )}

          {/* Section 4: Audit Access Log */}
          <section style={{ marginTop: "2rem" }}>
            <h2>{t("priv.log")}</h2>
            {!log || log.length === 0 ? (
              <p className="muted">{t("priv.log_none")}</p>
            ) : (
              log.map((r, i) => (
                <Card key={i} className="mb-1">
                  <div className="small-text">
                    <strong>{r.viewer}</strong> ({r.hospital || "LifeLine"}) accessed <em>{r.what}</em> on {fmtDate(r.ts, lang)} {new Date(r.ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
                  </div>
                </Card>
              ))
            )}
          </section>
        </>
      )}

      {/* Approval Dialog */}
      {approvingReq && (
        <Dialog
          open={true}
          onClose={() => setApprovingReq(null)}
          title={`Approve Record Access: ${approvingReq.doctor_name}`}
          confirmLabel="Grant Permission"
          confirmVariant="primary"
          onConfirm={handleApprove}
          busy={busy}
        >
          <p className="small-text muted">
            Select how long Dr. {approvingReq.doctor_name} may view your previous clinical records. Access will automatically expire.
          </p>

          <label className="field" style={{ marginTop: "1rem" }}>
            Duration of access:
            <select
              value={durationHours}
              onChange={(e) => setDurationHours(Number(e.target.value) as 24 | 168 | 720)}
            >
              <option value={24}>24 hours (Recommended for today's visit)</option>
              <option value={168}>7 days</option>
              <option value={720}>30 days</option>
            </select>
          </label>

          <div style={{ marginTop: "1rem" }}>
            <span className="field-label-text">Select record types to share:</span>
            <div className="row" style={{ gap: "1rem", marginTop: "0.5rem" }}>
              <label className="row" style={{ gap: "0.4rem", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={selectedHiTypes.includes("OPConsultNote")}
                  onChange={(e) =>
                    setSelectedHiTypes((prev) =>
                      e.target.checked ? [...prev, "OPConsultNote"] : prev.filter((x) => x !== "OPConsultNote")
                    )
                  }
                />
                <span>Consultation Notes (Diagnoses)</span>
              </label>
              <label className="row" style={{ gap: "0.4rem", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={selectedHiTypes.includes("Prescription")}
                  onChange={(e) =>
                    setSelectedHiTypes((prev) =>
                      e.target.checked ? [...prev, "Prescription"] : prev.filter((x) => x !== "Prescription")
                    )
                  }
                />
                <span>Prescriptions</span>
              </label>
            </div>
          </div>
        </Dialog>
      )}

      {/* Revoke Confirmation Dialog */}
      {revokingReq && (
        <Dialog
          open={true}
          onClose={() => setRevokingReq(null)}
          title="Revoke Medical Record Access"
          confirmLabel="Revoke Access Now"
          confirmVariant="warn"
          onConfirm={handleRevoke}
          busy={busy}
        >
          <p>
            Are you sure you want to revoke Dr. {revokingReq.doctor_name}'s permission to view your medical records?
          </p>
          <p className="muted small-text">
            They will immediately lose access to your past diagnostic and prescription records from outside facilities.
          </p>
        </Dialog>
      )}
    </div>
  );
}
