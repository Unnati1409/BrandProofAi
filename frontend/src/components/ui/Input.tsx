import React, { forwardRef, useId } from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
  error?: string;
  isMonospace?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className = '',
      label,
      helperText,
      error,
      isMonospace = false,
      id,
      disabled,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const inputId = id || generatedId;
    const errorId = `${inputId}-error`;
    const helperId = `${inputId}-helper`;

    return (
      <div className="w-full flex flex-col gap-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="text-xs font-semibold text-surface-700 select-none"
          >
            {label}
            {props.required && <span className="text-red-600 ml-0.5">*</span>}
          </label>
        )}
        <div className="relative">
          <input
            ref={ref}
            id={inputId}
            disabled={disabled}
            aria-invalid={!!error}
            aria-describedby={error ? errorId : helperText ? helperId : undefined}
            className={`w-full h-8.5 px-3 text-base bg-white border rounded transition-colors placeholder:text-surface-400 focus:outline-none focus:border-surface-900 focus:ring-1 focus:ring-surface-900 disabled:bg-surface-100 disabled:cursor-not-allowed ${
              isMonospace ? 'font-mono text-sm' : ''
            } ${
              error
                ? 'border-red-500 focus:border-red-600 focus:ring-red-600'
                : 'border-surface-300'
            } ${className}`}
            {...props}
          />
        </div>
        {error && (
          <p id={errorId} className="text-xs font-medium text-red-600" role="alert">
            {error}
          </p>
        )}
        {!error && helperText && (
          <p id={helperId} className="text-xs text-surface-500">
            {helperText}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
