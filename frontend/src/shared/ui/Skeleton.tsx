import React from "react";

export interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  radius?: string | number;
  lines?: number;
  className?: string;
}

export function Skeleton({
  width = "100%",
  height = "1.2rem",
  radius = "var(--radius-sm)",
  lines = 1,
  className = "",
}: SkeletonProps) {
  if (lines > 1) {
    return (
      <div className={`skeleton-group ${className}`.trim()} role="status" aria-label="Loading content">
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className="skeleton"
            style={{
              width: i === lines - 1 ? "75%" : width,
              height,
              borderRadius: radius,
              marginBottom: "0.5rem",
            }}
          />
        ))}
      </div>
    );
  }

  return (
    <div
      className={`skeleton ${className}`.trim()}
      role="status"
      aria-label="Loading content"
      style={{ width, height, borderRadius: radius }}
    />
  );
}
