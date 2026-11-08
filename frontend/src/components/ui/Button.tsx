import React, { forwardRef } from 'react';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'destructive';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className = '',
      variant = 'primary',
      size = 'md',
      isLoading = false,
      disabled = false,
      leftIcon,
      rightIcon,
      children,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center font-medium transition-colors select-none focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50 disabled:cursor-not-allowed border';

    const sizeStyles = {
      sm: 'h-7 px-2.5 text-xs rounded gap-1.5',
      md: 'h-8.5 px-3.5 text-base rounded gap-2',
      lg: 'h-10 px-4 text-md rounded-md gap-2.5',
    };

    const variantStyles = {
      primary:
        'bg-surface-900 text-white border-surface-900 hover:bg-surface-800 active:bg-surface-950 focus-visible:outline-surface-900',
      secondary:
        'bg-surface-100 text-surface-800 border-surface-200 hover:bg-surface-200 active:bg-surface-300 focus-visible:outline-surface-400',
      outline:
        'bg-white text-surface-800 border-surface-300 hover:bg-surface-50 active:bg-surface-100 focus-visible:outline-surface-400 shadow-subtle',
      ghost:
        'bg-transparent text-surface-700 border-transparent hover:bg-surface-100 active:bg-surface-200 focus-visible:outline-surface-400',
      destructive:
        'bg-red-600 text-white border-red-600 hover:bg-red-700 active:bg-red-800 focus-visible:outline-red-600',
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
        {...props}
      >
        {isLoading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
        ) : (
          leftIcon
        )}
        <span>{children}</span>
        {!isLoading && rightIcon}
      </button>
    );
  }
);

Button.displayName = 'Button';
