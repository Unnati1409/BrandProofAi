import React from 'react';

export interface PageHeaderProps {
  title: string;
  description?: string;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  breadcrumbs?: Array<{ label: string; href?: string }>;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  badge,
  actions,
  breadcrumbs,
}) => {
  return (
    <div className="flex flex-col gap-2 pb-4 border-b border-surface-200 mb-6">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav className="flex items-center gap-1.5 text-xs text-surface-400">
          {breadcrumbs.map((crumb, idx) => (
            <React.Fragment key={crumb.label}>
              {idx > 0 && <span>/</span>}
              {crumb.href ? (
                <a href={crumb.href} className="hover:text-surface-700 transition-colors">
                  {crumb.label}
                </a>
              ) : (
                <span className="text-surface-600 font-medium">{crumb.label}</span>
              )}
            </React.Fragment>
          ))}
        </nav>
      )}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <h1 className="text-xl font-bold text-surface-900 tracking-tight">{title}</h1>
          {badge}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      {description && (
        <p className="text-xs text-surface-500 max-w-2xl">{description}</p>
      )}
    </div>
  );
};
