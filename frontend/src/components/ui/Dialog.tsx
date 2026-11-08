import React, { useEffect } from 'react';
import { X } from 'lucide-react';

export interface DialogProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl';
}

export const Dialog: React.FC<DialogProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  maxWidth = 'md',
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const maxWidthStyles = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-2xl',
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-surface-950/40 backdrop-blur-none"
      role="dialog"
      aria-modal="true"
      aria-labelledby="dialog-title"
    >
      <div
        className={`w-full ${maxWidthStyles[maxWidth]} bg-white border border-surface-200 rounded-md shadow-popover overflow-hidden animate-in fade-in zoom-in-95 duration-150`}
      >
        <div className="flex items-center justify-between p-4 border-b border-surface-200">
          <div>
            <h2 id="dialog-title" className="text-base font-semibold text-surface-900">
              {title}
            </h2>
            {description && (
              <p className="text-xs text-surface-500 mt-0.5">{description}</p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1 text-surface-400 hover:text-surface-700 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-surface-900"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4">{children}</div>

        {footer && (
          <div className="flex items-center justify-end gap-2 p-3 bg-surface-50 border-t border-surface-200">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};
