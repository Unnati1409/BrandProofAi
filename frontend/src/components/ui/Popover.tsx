import React, { useEffect, useRef, useState } from 'react';

export interface PopoverProps {
  trigger: React.ReactNode;
  children: React.ReactNode;
  align?: 'left' | 'right';
  className?: string;
}

export const Popover: React.FC<PopoverProps> = ({
  trigger,
  children,
  align = 'left',
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [isOpen]);

  return (
    <div className="relative inline-block" ref={containerRef}>
      <div onClick={() => setIsOpen(!isOpen)} role="button" tabIndex={0}>
        {trigger}
      </div>
      {isOpen && (
        <div
          className={`absolute z-30 mt-1.5 w-64 bg-white border border-surface-200 rounded-md shadow-popover p-3 text-sm animate-in fade-in-50 duration-150 ${
            align === 'right' ? 'right-0' : 'left-0'
          } ${className}`}
        >
          {children}
        </div>
      )}
    </div>
  );
};
