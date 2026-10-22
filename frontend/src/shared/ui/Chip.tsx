import React, { type ButtonHTMLAttributes } from "react";
import { AlertTriangleIcon, CheckIcon, FlagIcon, ShieldAlertIcon } from "../icons";

export type ChipVariant = "default" | "emergency" | "urgent" | "routine" | "nurse";

export interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
  variant?: ChipVariant;
  icon?: React.ReactNode;
  label?: string;
}

export function Chip({
  children,
  active = false,
  variant = "default",
  icon,
  label,
  className = "",
  ...props
}: ChipProps) {
  let defaultIcon: React.ReactNode = null;
  if (variant === "emergency") {
    defaultIcon = <ShieldAlertIcon width={14} height={14} style={{ color: "var(--status-emergency-solid)" }} />;
  } else if (variant === "urgent") {
    defaultIcon = <AlertTriangleIcon width={14} height={14} style={{ color: "var(--status-urgent-solid)" }} />;
  } else if (variant === "routine") {
    defaultIcon = <CheckIcon width={14} height={14} style={{ color: "var(--status-routine-solid)" }} />;
  } else if (variant === "nurse") {
    defaultIcon = <FlagIcon width={14} height={14} style={{ color: "var(--primary)" }} />;
  }

  const finalIcon = icon !== undefined ? icon : defaultIcon;

  return (
    <button
      type="button"
      className={`chip chip-${variant} ${active ? "on" : ""} ${className}`.trim()}
      aria-pressed={props.onClick ? active : undefined}
      {...props}
    >
      {finalIcon && <span className="chip-icon" aria-hidden="true">{finalIcon}</span>}
      <span>{children || label}</span>
    </button>
  );
}

export function StatusPill({
  variant,
  label,
  icon,
  className = "",
}: {
  variant: "emergency" | "urgent" | "same-day" | "routine" | "nurse" | "neutral";
  label: string;
  icon?: React.ReactNode;
  className?: string;
}) {
  const normVariant = variant === "same-day" ? "urgent" : variant;
  return (
    <span className={`pill ${normVariant} ${className}`.trim()}>
      {icon && <span style={{ marginRight: 4 }} aria-hidden="true">{icon}</span>}
      {label}
    </span>
  );
}
