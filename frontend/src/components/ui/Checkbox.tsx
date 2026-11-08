import React, { forwardRef, useId } from 'react';
import { Check } from 'lucide-react';

export interface CheckboxProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  description?: string;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className = '', label, description, id, checked, disabled, ...props }, ref) => {
    const generatedId = useId();
    const checkboxId = id || generatedId;

    return (
      <label
        htmlFor={checkboxId}
        className={`flex items-start gap-2.5 cursor-pointer select-none ${
          disabled ? 'opacity-50 cursor-not-allowed' : ''
        } ${className}`}
      >
        <div className="relative flex items-center justify-center mt-0.5">
          <input
            ref={ref}
            type="checkbox"
            id={checkboxId}
            checked={checked}
            disabled={disabled}
            className="peer sr-only"
            {...props}
          />
          <div className="h-4 w-4 rounded border border-surface-300 bg-white transition-colors peer-checked:bg-surface-900 peer-checked:border-surface-900 peer-focus-visible:ring-2 peer-focus-visible:ring-surface-900 peer-focus-visible:ring-offset-1 flex items-center justify-center">
            <Check
              className="h-3 w-3 text-white opacity-0 peer-checked:opacity-100 transition-opacity"
              strokeWidth={3}
              aria-hidden="true"
            />
          </div>
        </div>
        {(label || description) && (
          <div className="flex flex-col">
            {label && (
              <span className="text-base font-medium text-surface-900 leading-tight">
                {label}
              </span>
            )}
            {description && (
              <span className="text-xs text-surface-500 mt-0.5 leading-normal">
                {description}
              </span>
            )}
          </div>
        )}
      </label>
    );
  }
);

Checkbox.displayName = 'Checkbox';
