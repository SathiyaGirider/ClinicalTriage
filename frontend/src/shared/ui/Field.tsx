import React, { type ReactNode, useId } from "react";

export interface FieldProps {
  label: ReactNode;
  error?: string | null;
  hint?: ReactNode;
  required?: boolean;
  children: React.ReactElement;
  className?: string;
}

export function Field({ label, error, hint, required, children, className = "" }: FieldProps) {
  const generatedId = useId();
  const childId = children.props.id || generatedId;
  const errorId = `${childId}-error`;
  const hintId = `${childId}-hint`;

  const ariaDescribedBy = [
    error ? errorId : null,
    hint ? hintId : null,
    children.props["aria-describedby"],
  ].filter(Boolean).join(" ") || undefined;

  const clonedChild = React.cloneElement(children, {
    id: childId,
    "aria-invalid": error ? true : undefined,
    "aria-describedby": ariaDescribedBy,
    required: required || children.props.required,
  });

  return (
    <div className={`field-group ${error ? "has-error" : ""} ${className}`.trim()}>
      <label htmlFor={childId} className="field-label">
        <span className="field-label-text">{label}</span>
        {required && <span className="field-required" aria-hidden="true">*</span>}
      </label>
      {clonedChild}
      {hint && !error && (
        <div id={hintId} className="field-hint small-text muted">
          {hint}
        </div>
      )}
      {error && (
        <div id={errorId} className="field-error small-text" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
