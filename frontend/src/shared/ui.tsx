import { type ReactNode } from "react";
import { ApiError } from "./api";
import { useI18n } from "./i18n";

export function DemoBanner() {
  const { t } = useI18n();
  return (
    <div className="banner banner-demo" role="note">
      <span aria-hidden>🧪</span> {t("banner.demo")}
    </div>
  );
}

export function SafetyBanner() {
  const { t } = useI18n();
  return (
    <div className="banner banner-ai" role="note">
      <span aria-hidden>🩺</span> {t("banner.ai")}
    </div>
  );
}

export function Loading() {
  const { t } = useI18n();
  return (
    <p className="muted" role="status">
      {t("common.loading")}
    </p>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  if (!error) return null;
  const offline = error instanceof ApiError && error.offline;
  const msg = offline ? t("common.offline") : error instanceof Error ? error.message : t("err.generic");
  return (
    <div className="error" role="alert">
      <span aria-hidden>{offline ? "📶" : "⚠️"}</span> {msg}
      {onRetry && (
        <button className="btn small" onClick={onRetry}>
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}
