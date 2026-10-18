import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, post, setToken, setUnauthorizedHandler } from "./api";

export type Me = {
  id: number;
  email: string;
  full_name: string;
  role: "patient" | "nurse" | "doctor";
  hospital_id?: number | null;
  hospital_name?: string | null;
  doctor_id?: number | null;
  language?: "en" | "ta" | null;
  age?: string | null;
  area?: string | null;
  share_history_consent?: boolean | null;
};

type Ctx = {
  me: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<Me>;
  register: (body: Record<string, unknown>) => Promise<Me>;
  logout: () => void;
  refresh: () => Promise<void>;
};

const AuthCtx = createContext<Ctx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setMe(null);
      return;
    }
    try {
      setMe(await api<Me>("/auth/me"));
    } catch {
      setMe(null);
    }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setToken(null);
      setMe(null);
    });
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const login = async (email: string, password: string) => {
    const r = await post<{ access_token: string }>("/auth/login", { email, password });
    setToken(r.access_token);
    const m = await api<Me>("/auth/me");
    setMe(m);
    return m;
  };
  const register = async (body: Record<string, unknown>) => {
    const r = await post<{ access_token: string }>("/auth/register", body);
    setToken(r.access_token);
    const m = await api<Me>("/auth/me");
    setMe(m);
    return m;
  };
  const logout = () => {
    setToken(null);
    setMe(null);
  };
  return <AuthCtx.Provider value={{ me, loading, login, register, logout, refresh }}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  const c = useContext(AuthCtx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}

export function homeFor(role?: string) {
  return role === "nurse" ? "/staff/nurse" : role === "doctor" ? "/staff/doctor" : "/patient";
}
