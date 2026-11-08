import React from 'react';

export interface TabItem {
  id: string;
  label: string;
  count?: number;
}

export interface TabsProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (tabId: string) => void;
  className?: string;
}

export const Tabs: React.FC<TabsProps> = ({
  tabs,
  activeTab,
  onChange,
  className = '',
}) => {
  return (
    <div className={`border-b border-surface-200 ${className}`}>
      <nav className="flex space-x-6" aria-label="Tabs" role="tablist">
        {tabs.map((tab) => {
          const isActive = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={isActive}
              aria-controls={`panel-${tab.id}`}
              onClick={() => onChange(tab.id)}
              className={`py-2 px-1 border-b-2 font-medium text-xs tracking-tight transition-colors flex items-center gap-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-surface-900 focus-visible:ring-offset-2 ${
                isActive
                  ? 'border-surface-900 text-surface-900 font-semibold'
                  : 'border-transparent text-surface-500 hover:text-surface-700 hover:border-surface-300'
              }`}
            >
              <span>{tab.label}</span>
              {typeof tab.count === 'number' && (
                <span
                  className={`px-1.5 py-0.2 text-2xs rounded tabular-nums ${
                    isActive
                      ? 'bg-surface-900 text-white'
                      : 'bg-surface-100 text-surface-600'
                  }`}
                >
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </nav>
    </div>
  );
};
