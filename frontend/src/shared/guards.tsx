import { type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { homeFor, useAuth } from "./auth";
import { Loading } from "./ui";

export function RequireRole({ role, children }: { role: "patient" | "nurse" | "doctor"; children: ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return <Loading />;
  if (!me) return <Navigate to="/login" replace />;
  if (me.role !== role) return <Navigate to={homeFor(me.role)} replace />;
  return <>{children}</>;
}
