import React, { useEffect } from 'react';
import { X } from 'lucide-react';

export interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  width?: 'md' | 'lg' | 'xl';
}

export const Drawer: React.FC<DrawerProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  width = 'lg',
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

  const widthStyles = {
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-2xl',
  };

  return (
    <div
      className="fixed inset-0 z-50 overflow-hidden bg-surface-950/30"
      role="dialog"
      aria-modal="true"
    >
      <div className="absolute inset-y-0 right-0 max-w-full flex pl-10">
        <div
          className={`w-screen ${widthStyles[width]} bg-white border-l border-surface-200 shadow-popover flex flex-col`}
        >
          <div className="flex items-center justify-between p-4 border-b border-surface-200">
            <div>
              <h2 className="text-base font-semibold text-surface-900">{title}</h2>
              {description && (
                <p className="text-xs text-surface-500 mt-0.5">{description}</p>
              )}
            </div>
            <button
              onClick={onClose}
              aria-label="Close drawer"
              className="p-1 text-surface-400 hover:text-surface-700 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-surface-900"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4">{children}</div>

          {footer && (
            <div className="flex items-center justify-end gap-2 p-3 bg-surface-50 border-t border-surface-200">
              {footer}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
