import { useEffect, useRef, type ReactNode } from "react";
import { Button } from "./Button";

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm?: () => void;
  confirmVariant?: "primary" | "danger" | "warn";
  busy?: boolean;
}

export function Dialog({
  open,
  onClose,
  title,
  children,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  confirmVariant = "primary",
  busy = false,
}: DialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose, busy]);

  if (!open) return null;

  return (
    <div className="dialog-overlay" onClick={() => !busy && onClose()} aria-hidden="true">
      <div
        ref={dialogRef}
        className="dialog-box"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="dialog-header spread">
          <h2 id="dialog-title">{title}</h2>
          <Button variant="ghost" size="small" onClick={onClose} disabled={busy} aria-label="Close dialog">
            ✕
          </Button>
        </div>
        <div className="dialog-body">{children}</div>
        <div className="dialog-footer row" style={{ justifyContent: "flex-end", gap: "0.5rem" }}>
          <Button variant="outline" size="small" onClick={onClose} disabled={busy}>
            {cancelLabel}
          </Button>
          {onConfirm && (
            <Button variant={confirmVariant} size="small" onClick={onConfirm} busy={busy}>
              {confirmLabel}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
