import React, { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import { AlertTriangleIcon, CheckIcon, ShieldAlertIcon } from "../icons";

export type ToastType = "info" | "success" | "warn" | "error";

export interface ToastItem {
  id: string;
  message: string;
  type?: ToastType;
  duration?: number;
}

interface ToastContextValue {
  showToast: (message: string, type?: ToastType, duration?: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const showToast = useCallback((message: string, type: ToastType = "info", duration = 4000) => {
    const id = Math.random().toString(36).slice(2, 9);
    setToasts((prev) => [...prev, { id, message, type, duration }]);

    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration);
  }, []);

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="toast-container" role="region" aria-label="Notifications" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.type || "info"}`} role="status">
            <span className="toast-icon" aria-hidden="true">
              {toast.type === "success" && <CheckIcon width={16} height={16} />}
              {toast.type === "error" && <ShieldAlertIcon width={16} height={16} />}
              {toast.type === "warn" && <AlertTriangleIcon width={16} height={16} />}
            </span>
            <span className="toast-message">{toast.message}</span>
            <button
              className="toast-close btn ghost small"
              onClick={() => removeToast(toast.id)}
              aria-label="Dismiss notification"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    return {
      showToast: (msg: string) => console.log("Toast:", msg),
    };
  }
  return ctx;
}
