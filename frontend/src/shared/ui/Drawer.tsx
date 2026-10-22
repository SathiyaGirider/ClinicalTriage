import { useEffect, useRef, type ReactNode } from "react";
import { Button } from "./Button";

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  width?: string | number;
}

export function Drawer({ open, onClose, title, children, footer, width = 480 }: DrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="drawer-overlay" onClick={onClose} aria-hidden="true">
      <aside
        ref={drawerRef}
        className="drawer-panel"
        style={{ maxWidth: width }}
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === "string" ? title : undefined}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="drawer-header spread">
          <h2 className="drawer-title">{title}</h2>
          <Button variant="ghost" size="small" onClick={onClose} aria-label="Close drawer">
            ✕
          </Button>
        </div>
        <div className="drawer-body">{children}</div>
        {footer && <div className="drawer-footer">{footer}</div>}
      </aside>
    </div>
  );
}
