import React from 'react';
import { X } from 'lucide-react';

export interface TagProps extends React.HTMLAttributes<HTMLSpanElement> {
  onRemove?: () => void;
  isMonospace?: boolean;
}

export const Tag: React.FC<TagProps> = ({
  className = '',
  onRemove,
  isMonospace = false,
  children,
  ...props
}) => {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-xs bg-surface-100 text-surface-800 border border-surface-200 rounded ${
        isMonospace ? 'font-mono' : 'font-medium'
      } ${className}`}
      {...props}
    >
      <span>{children}</span>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="text-surface-400 hover:text-surface-700 transition-colors focus:outline-none"
          aria-label="Remove tag"
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </span>
  );
};
