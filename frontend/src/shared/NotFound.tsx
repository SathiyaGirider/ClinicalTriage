import { Link } from "react-router-dom";
import { homeFor, useAuth } from "./auth";
import { AlertTriangleIcon } from "./icons";
import { Layout } from "./Layout";
import { Button } from "./ui";

export default function NotFound() {
  const { me } = useAuth();
  const returnPath = me ? homeFor(me.role) : "/login";

  return (
    <Layout>
      <div className="card" style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
        <div style={{ display: "inline-flex", padding: "1rem", background: "var(--status-urgent-bg)", borderRadius: "50%", marginBottom: "1rem" }}>
          <AlertTriangleIcon width={40} height={40} style={{ color: "var(--status-urgent-solid)" }} />
        </div>
        <h1 style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>Page Not Found</h1>
        <p className="muted" style={{ maxWidth: 440, margin: "0 auto 1.5rem" }}>
          The requested page or record does not exist or has been relocated.
        </p>
        <Link to={returnPath}>
          <Button variant="primary">Return Home</Button>
        </Link>
      </div>
    </Layout>
  );
}
