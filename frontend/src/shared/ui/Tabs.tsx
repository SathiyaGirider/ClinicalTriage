import React, { type ReactNode } from "react";

export interface TabItem {
  id: string;
  label: ReactNode;
  count?: number;
}

export interface TabsProps {
  tabs: TabItem[];
  activeId: string;
  onChange: (id: string) => void;
  className?: string;
}

export function Tabs({ tabs, activeId, onChange, className = "" }: TabsProps) {
  return (
    <div className={`clinical-tabs ${className}`.trim()} role="tablist">
      {tabs.map((tab) => {
        const isActive = tab.id === activeId;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            className={`tab-btn ${isActive ? "active" : ""}`}
            onClick={() => onChange(tab.id)}
          >
            <span>{tab.label}</span>
            {tab.count !== undefined && (
              <span className={`tab-badge ${isActive ? "active" : ""}`}>
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
