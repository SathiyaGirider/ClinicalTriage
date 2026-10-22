import { type ReactNode } from "react";
import { ApiError } from "../api";
import { useI18n } from "../i18n";
import { AlertTriangleIcon, HospitalIcon, ShieldAlertIcon } from "../icons";

export function DemoBanner() {
  const { t } = useI18n();
  return (
    <div className="banner banner-demo" role="note">
      <HospitalIcon width={16} height={16} style={{ flexShrink: 0 }} />
      <span>{t("banner.demo")}</span>
    </div>
  );
}

export function SafetyBanner() {
  const { t } = useI18n();
  return (
    <div className="banner banner-ai" role="note">
      <ShieldAlertIcon width={15} height={15} style={{ flexShrink: 0 }} />
      <span>{t("banner.ai")}</span>
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
      <AlertTriangleIcon width={18} height={18} style={{ flexShrink: 0 }} />
      <span style={{ flex: 1 }}>{msg}</span>
      {onRetry && (
        <button className="btn small secondary" onClick={onRetry}>
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}
