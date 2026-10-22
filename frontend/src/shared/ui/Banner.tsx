import React, { type ReactNode } from "react";
import { AlertTriangleIcon, CheckIcon, HospitalIcon, ShieldAlertIcon } from "../icons";

export type BannerVariant = "info" | "demo" | "ai" | "warn" | "emergency" | "routine";

export interface BannerProps {
  variant?: BannerVariant;
  children: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function Banner({
  variant = "info",
  children,
  icon,
  action,
  className = "",
}: BannerProps) {
  let defaultIcon: ReactNode = null;
  if (variant === "demo") defaultIcon = <HospitalIcon width={16} height={16} />;
  else if (variant === "ai") defaultIcon = <ShieldAlertIcon width={16} height={16} />;
  else if (variant === "warn") defaultIcon = <AlertTriangleIcon width={16} height={16} />;
  else if (variant === "emergency") defaultIcon = <AlertTriangleIcon width={16} height={16} />;
  else if (variant === "routine") defaultIcon = <CheckIcon width={16} height={16} />;

  const finalIcon = icon !== undefined ? icon : defaultIcon;

  return (
    <div className={`clinical-banner banner-${variant} ${className}`.trim()} role="note">
      {finalIcon && <span className="banner-icon" aria-hidden="true">{finalIcon}</span>}
      <div className="banner-content">{children}</div>
      {action && <div className="banner-action">{action}</div>}
    </div>
  );
}
