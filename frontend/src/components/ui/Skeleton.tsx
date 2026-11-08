import React from 'react';

export interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'rectangular' | 'circular';
  width?: string | number;
  height?: string | number;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  className = '',
  variant = 'text',
  width,
  height,
}) => {
  const variantStyles = {
    text: 'h-4 w-full rounded',
    rectangular: 'rounded',
    circular: 'rounded-full',
  };

  return (
    <div
      style={{ width, height }}
      className={`animate-pulse bg-surface-200 ${variantStyles[variant]} ${className}`}
      aria-hidden="true"
    />
  );
};
