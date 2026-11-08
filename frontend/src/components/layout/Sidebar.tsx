import React from 'react';
import {
  Shield,
  BookMarked,
  CheckSquare,
  FileText,
  Clock,
  Palette,
  Users,
  Settings,
  History,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  badge?: number;
}

export interface SidebarProps {
  activeNav: string;
  onNavSelect: (id: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeNav,
  onNavSelect,
  isCollapsed,
  onToggleCollapse,
}) => {
  const navItems: NavItem[] = [
    { id: 'dashboard', label: 'Overview', icon: <Shield className="h-4 w-4" /> },
    { id: 'guidelines', label: 'Guidelines & Candidates', icon: <BookMarked className="h-4 w-4" /> },
    { id: 'rules', label: 'Rule Catalogue', icon: <CheckSquare className="h-4 w-4" /> },
    { id: 'facts', label: 'Approved Fact Base', icon: <FileText className="h-4 w-4" /> },
    { id: 'assets', label: 'Asset Library', icon: <Palette className="h-4 w-4" /> },
    { id: 'content', label: 'Content Submissions', icon: <FileText className="h-4 w-4" />, badge: 3 },
    { id: 'review_queue', label: 'Review Queue', icon: <Clock className="h-4 w-4" />, badge: 2 },
    { id: 'members', label: 'Members & Roles', icon: <Users className="h-4 w-4" /> },
    { id: 'audit', label: 'Audit Trail', icon: <History className="h-4 w-4" /> },
    { id: 'settings', label: 'Settings & AI Disclosure', icon: <Settings className="h-4 w-4" /> },
  ];

  return (
    <aside
      className={`h-screen bg-white border-r border-surface-200 flex flex-col transition-all duration-200 select-none ${
        isCollapsed ? 'w-14' : 'w-60'
      }`}
    >
      {/* Brand Header */}
      <div className="h-12 border-b border-surface-200 flex items-center justify-between px-3">
        {!isCollapsed && (
          <div className="flex items-center gap-2">
            <div className="h-6 w-6 rounded bg-surface-900 flex items-center justify-center text-white font-bold text-xs">
              B
            </div>
            <span className="font-semibold text-xs tracking-tight text-surface-900">
              BrandProof AI
            </span>
          </div>
        )}
        {isCollapsed && (
          <div className="h-6 w-6 mx-auto rounded bg-surface-900 flex items-center justify-center text-white font-bold text-xs">
            B
          </div>
        )}
        <button
          onClick={onToggleCollapse}
          className="p-1 rounded text-surface-400 hover:text-surface-700 hover:bg-surface-100 transition-colors focus:outline-none focus:ring-1 focus:ring-surface-900"
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
        </button>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 overflow-y-auto p-2 space-y-1">
        {navItems.map((item) => {
          const isActive = activeNav === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavSelect(item.id)}
              className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-surface-900 ${
                isActive
                  ? 'bg-surface-100 text-surface-900 font-semibold'
                  : 'text-surface-600 hover:bg-surface-50 hover:text-surface-900'
              }`}
              title={isCollapsed ? item.label : undefined}
            >
              <div className="shrink-0 text-surface-500">{item.icon}</div>
              {!isCollapsed && <span className="flex-1 text-left truncate">{item.label}</span>}
              {!isCollapsed && typeof item.badge === 'number' && (
                <span className="px-1.5 py-0.2 text-2xs rounded bg-surface-200 text-surface-700 tabular-nums">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Seed Brand Tag */}
      {!isCollapsed && (
        <div className="p-3 border-t border-surface-200 bg-surface-50 text-2xs text-surface-500">
          <p className="font-semibold text-surface-700">Team SAKHI</p>
          <p className="truncate">AuraHealth Technologies Demo</p>
        </div>
      )}
    </aside>
  );
};
