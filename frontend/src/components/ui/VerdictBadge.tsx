import React from 'react';
import { CheckCircle2, XCircle, HelpCircle, AlertCircle } from 'lucide-react';
import { ClaimVerdict } from '../../types';

export interface VerdictBadgeProps {
  verdict: ClaimVerdict;
  className?: string;
}

export const VerdictBadge: React.FC<VerdictBadgeProps> = ({
  verdict,
  className = '',
}) => {
  const config = {
    supported: {
      label: 'Supported by Approved Source',
      icon: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700 shrink-0" aria-hidden="true" />,
      styles: 'bg-emerald-50 text-emerald-900 border-emerald-300',
    },
    contradicted: {
      label: 'Contradicted by Approved Source',
      icon: <XCircle className="h-3.5 w-3.5 text-red-700 shrink-0" aria-hidden="true" />,
      styles: 'bg-red-50 text-red-900 border-red-300 font-semibold',
    },
    unsupported: {
      label: 'Unsupported by Approved Source',
      icon: <AlertCircle className="h-3.5 w-3.5 text-amber-700 shrink-0" aria-hidden="true" />,
      styles: 'bg-amber-50 text-amber-900 border-amber-300',
    },
    needs_human_review: {
      label: 'Needs Human Review',
      icon: <HelpCircle className="h-3.5 w-3.5 text-indigo-700 shrink-0" aria-hidden="true" />,
      styles: 'bg-indigo-50 text-indigo-900 border-indigo-300 font-medium',
    },
  };

  const item = config[verdict];

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
