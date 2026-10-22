import { Link } from "react-router-dom";
import { homeFor, useAuth } from "./auth";
import { ShieldAlertIcon } from "./icons";
import { Layout } from "./Layout";
import { Button } from "./ui";

export default function Forbidden() {
  const { me } = useAuth();
  const returnPath = me ? homeFor(me.role) : "/login";

  return (
    <Layout>
      <div className="card" style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
        <div style={{ display: "inline-flex", padding: "1rem", background: "var(--status-emergency-bg)", borderRadius: "50%", marginBottom: "1rem" }}>
          <ShieldAlertIcon width={40} height={40} style={{ color: "var(--status-emergency-solid)" }} />
        </div>
        <h1 style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>Access Restricted</h1>
        <p className="muted" style={{ maxWidth: 440, margin: "0 auto 1.5rem" }}>
          You do not have authorization to view this clinical workspace or patient record.
        </p>
        <Link to={returnPath}>
          <Button variant="primary">Return to Safe Workspace</Button>
        </Link>
      </div>
    </Layout>
  );
}
