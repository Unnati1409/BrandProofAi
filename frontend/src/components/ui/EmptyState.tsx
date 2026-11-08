import React from 'react';

export interface EmptyStateProps {
  title: string;
  description: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  action,
  icon,
  className = '',
}) => {
  return (
    <div
      className={`flex flex-col items-center justify-center p-8 text-center border border-dashed border-surface-300 rounded-md bg-surface-50/50 ${className}`}
    >
      {icon && <div className="text-surface-400 mb-3">{icon}</div>}
      <h3 className="text-base font-semibold text-surface-900">{title}</h3>
      <p className="text-xs text-surface-500 mt-1 max-w-sm leading-relaxed">
        {description}
      </p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
};
