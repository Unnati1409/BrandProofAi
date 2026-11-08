import React, { forwardRef, useId } from 'react';

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  helperText?: string;
  error?: string;
  isMonospace?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      className = '',
      label,
      helperText,
      error,
      isMonospace = false,
      id,
      disabled,
      rows = 4,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const textareaId = id || generatedId;
    const errorId = `${textareaId}-error`;
    const helperId = `${textareaId}-helper`;

    return (
      <div className="w-full flex flex-col gap-1.5">
        {label && (
          <label
            htmlFor={textareaId}
            className="text-xs font-semibold text-surface-700 select-none"
          >
            {label}
            {props.required && <span className="text-red-600 ml-0.5">*</span>}
          </label>
        )}
        <div className="relative">
          <textarea
            ref={ref}
            id={textareaId}
            rows={rows}
            disabled={disabled}
            aria-invalid={!!error}
            aria-describedby={error ? errorId : helperText ? helperId : undefined}
            className={`w-full p-3 text-base bg-white border rounded transition-colors placeholder:text-surface-400 focus:outline-none focus:border-surface-900 focus:ring-1 focus:ring-surface-900 disabled:bg-surface-100 disabled:cursor-not-allowed ${
              isMonospace ? 'font-mono text-sm leading-relaxed' : ''
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

Textarea.displayName = 'Textarea';
