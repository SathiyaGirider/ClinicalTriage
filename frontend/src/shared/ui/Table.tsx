import React, { type TableHTMLAttributes } from "react";

export interface TableProps extends TableHTMLAttributes<HTMLTableElement> {
  caption?: string;
  dense?: boolean;
}

export function Table({ children, caption, dense = true, className = "", ...props }: TableProps) {
  return (
    <div className="table-container">
      <table className={`clinical-table ${dense ? "dense" : ""} ${className}`.trim()} {...props}>
        {caption && <caption className="sr-only">{caption}</caption>}
        {children}
      </table>
    </div>
  );
}
