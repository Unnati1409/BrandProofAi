import React from 'react';
import { AlertTriangle, AlertOctagon, Info } from 'lucide-react';
import { FindingSeverity } from '../../types';

export interface SeverityBadgeProps {
  severity: FindingSeverity;
  className?: string;
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({
  severity,
  className = '',
}) => {
  const config = {
    low: {
      label: 'Low Severity',
      icon: <Info className="h-3 w-3 text-amber-700 shrink-0" aria-hidden="true" />,
      styles: 'bg-amber-50 text-amber-800 border-amber-300',
    },
    medium: {
      label: 'Medium Severity',
      icon: <AlertTriangle className="h-3 w-3 text-orange-700 shrink-0" aria-hidden="true" />,
      styles: 'bg-orange-50 text-orange-800 border-orange-300',
    },
    high: {
      label: 'High Severity',
      icon: <AlertOctagon className="h-3 w-3 text-red-700 shrink-0" aria-hidden="true" />,
      styles: 'bg-red-50 text-red-800 border-red-300 font-semibold',
    },
  };

  const item = config[severity];

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-xs rounded border select-none ${item.styles} ${className}`}
      aria-label={item.label}
    >
      {item.icon}
      <span>{item.label}</span>
    </span>
  );
};
