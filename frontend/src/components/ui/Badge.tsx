import React from 'react';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'neutral' | 'info' | 'success' | 'warning' | 'error';
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  className = '',
  variant = 'neutral',
  size = 'md',
  children,
  ...props
}) => {
  const sizeStyles = {
    sm: 'px-1.5 py-0.5 text-2xs leading-none font-medium',
    md: 'px-2 py-0.5 text-xs font-medium',
  };

  const variantStyles = {
    neutral: 'bg-surface-100 text-surface-700 border-surface-200',
    info: 'bg-blue-50 text-blue-800 border-blue-200',
    success: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    warning: 'bg-amber-50 text-amber-800 border-amber-200',
    error: 'bg-red-50 text-red-800 border-red-200',
  };

  return (
    <span
      className={`inline-flex items-center gap-1 border rounded tabular-nums select-none ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
};
