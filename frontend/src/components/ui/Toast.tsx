import React from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

export interface ToastItem {
  id: string;
  type: 'success' | 'error' | 'info';
  message: string;
}

export interface ToastProps {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}

export const Toast: React.FC<ToastProps> = ({ toasts, onDismiss }) => {
  if (toasts.length === 0) return null;

  const iconMap = {
    success: <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />,
    error: <AlertCircle className="h-4 w-4 text-red-600 shrink-0" />,
    info: <Info className="h-4 w-4 text-blue-600 shrink-0" />,
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="pointer-events-auto flex items-start gap-2.5 p-3 bg-white border border-surface-200 rounded-md shadow-popover text-sm text-surface-800 animate-in slide-in-from-bottom-2 duration-150"
        >
          {iconMap[toast.type]}
          <div className="flex-1 text-xs font-medium leading-tight pt-0.5">
            {toast.message}
          </div>
          <button
            onClick={() => onDismiss(toast.id)}
            className="text-surface-400 hover:text-surface-600 transition-colors focus:outline-none"
            aria-label="Dismiss toast"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
};
