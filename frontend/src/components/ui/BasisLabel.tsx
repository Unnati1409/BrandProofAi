import React from 'react';
import { Cpu, Scale } from 'lucide-react';
import { FindingBasis } from '../../types';

export interface BasisLabelProps {
  basis: FindingBasis;
  className?: string;
}

export const BasisLabel: React.FC<BasisLabelProps> = ({
  basis,
  className = '',
}) => {
  if (basis === 'rule_based') {
    return (
      <span
        className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-2xs font-semibold uppercase tracking-wider rounded border bg-surface-100 text-surface-800 border-surface-300 select-none ${className}`}
        title="Evaluated via deterministic code verification"
      >
        <Scale className="h-3 w-3 text-surface-600" aria-hidden="true" />
        <span>Rule-based</span>
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-2xs font-semibold uppercase tracking-wider rounded border bg-blue-50 text-blue-900 border-blue-200 select-none ${className}`}
      title="Evaluated via grounded AI reasoning (Advisory only)"
    >
      <Cpu className="h-3 w-3 text-blue-700" aria-hidden="true" />
      <span>AI-assisted (Advisory)</span>
    </span>
  );
};
