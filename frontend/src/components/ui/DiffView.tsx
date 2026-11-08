import React from 'react';

export interface DiffViewProps {
  originalText: string;
  suggestedText: string;
  className?: string;
}

export const DiffView: React.FC<DiffViewProps> = ({
  originalText,
  suggestedText,
  className = '',
}) => {
  return (
    <div className={`grid grid-cols-1 md:grid-cols-2 gap-2 text-xs font-mono rounded border border-surface-200 bg-surface-50 p-2.5 ${className}`}>
      <div className="flex flex-col gap-1 border-r-0 md:border-r border-surface-200 md:pr-2.5">
        <span className="text-2xs font-sans font-semibold text-red-700 uppercase tracking-wider select-none">
          Current Content
        </span>
        <div className="p-2 bg-red-50 text-red-900 border border-red-200 rounded leading-relaxed whitespace-pre-wrap">
          <span className="select-none font-bold mr-1.5 text-red-500">-</span>
          {originalText}
        </div>
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-2xs font-sans font-semibold text-emerald-700 uppercase tracking-wider select-none">
          Approved Sourced Rewrite
        </span>
        <div className="p-2 bg-emerald-50 text-emerald-900 border border-emerald-200 rounded leading-relaxed whitespace-pre-wrap">
          <span className="select-none font-bold mr-1.5 text-emerald-500">+</span>
          {suggestedText}
        </div>
      </div>
    </div>
  );
};
