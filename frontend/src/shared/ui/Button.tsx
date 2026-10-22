import React, { type ButtonHTMLAttributes, forwardRef } from "react";

export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost" | "danger" | "warn";
export type ButtonSize = "default" | "small" | "large";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  busy?: boolean;
  icon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ children, variant = "primary", size = "default", busy = false, disabled, icon, className = "", ...props }, ref) => {
    const classes = [
      "btn",
      variant !== "primary" ? variant : "",
      size === "small" ? "small" : size === "large" ? "large" : "",
      busy ? "busy" : "",
      className,
    ].filter(Boolean).join(" ");

    return (
      <button
        ref={ref}
        className={classes}
        disabled={disabled || busy}
        aria-busy={busy}
        {...props}
      >
        {busy ? (
          <span className="spinner" aria-hidden="true" />
        ) : icon ? (
          <span className="btn-icon" aria-hidden="true">{icon}</span>
        ) : null}
        <span>{children}</span>
      </button>
    );
  }
);

Button.displayName = "Button";
