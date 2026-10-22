import { type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./auth";
import Forbidden from "./Forbidden";
import { Loading } from "./ui";

export function RequireRole({ role, children }: { role: "patient" | "nurse" | "doctor"; children: ReactNode }) {
  const { me, loading } = useAuth();
  const location = useLocation();

  if (loading) return <Loading />;
  if (!me) {
    const returnTo = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?return_to=${returnTo}`} replace />;
  }
  if (me.role !== role) {
    return <Forbidden />;
  }
  return <>{children}</>;
}

