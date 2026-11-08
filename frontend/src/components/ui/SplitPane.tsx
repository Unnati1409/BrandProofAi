import React from 'react';

export interface SplitPaneProps {
  left: React.ReactNode;
  right: React.ReactNode;
  leftWidth?: string;
  className?: string;
}

export const SplitPane: React.FC<SplitPaneProps> = ({
  left,
  right,
  leftWidth = 'w-1/2',
  className = '',
}) => {
  return (
    <div className={`flex flex-col lg:flex-row w-full h-full border border-surface-200 rounded-md overflow-hidden bg-white shadow-subtle ${className}`}>
      <div className={`${leftWidth} border-b lg:border-b-0 lg:border-r border-surface-200 overflow-y-auto`}>
        {left}
      </div>
      <div className="flex-1 overflow-y-auto bg-surface-50/30">
        {right}
      </div>
    </div>
  );
};
