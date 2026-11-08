import React from 'react';
import { Building2, ChevronDown, Sparkles, LogOut } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { useAuth } from '../../context/AuthContext';
import { useWorkspace } from '../../context/WorkspaceContext';

export interface TopBarProps {
  currentWorkspace?: string;
  userRole?: string;
  userEmail?: string;
  isAiEnabled?: boolean;
  onSwitchWorkspace?: () => void;
  onLogout?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  currentWorkspace: propWorkspace,
  userRole: propRole,
  userEmail: propEmail,
  isAiEnabled: propAiEnabled,
  onSwitchWorkspace,
  onLogout,
}) => {
  // Try to use contexts if available
  let authContext: ReturnType<typeof useAuth> | null = null;
  let wsContext: ReturnType<typeof useWorkspace> | null = null;

  try {
    authContext = useAuth();
  } catch {
    // context not present in isolated unit tests
  }

  try {
    wsContext = useWorkspace();
  } catch {
    // context not present in isolated unit tests
  }

  const workspaceName = propWorkspace || wsContext?.activeWorkspace?.name || 'AuraHealth Technologies';
  const isAiActive = propAiEnabled !== undefined ? propAiEnabled : !!wsContext?.activeWorkspace?.ai_enabled;
  const email = propEmail || authContext?.user?.email || 'compliance@aurahealth.demo';
  const roles = wsContext?.currentUserRoles || (propRole ? [propRole] : ['brand_owner']);

  const handleLogout = () => {
    if (onLogout) {
      onLogout();
    } else if (authContext?.logout) {
      authContext.logout();
    }
  };

  return (
    <header className="h-12 bg-white border-b border-surface-200 px-4 flex items-center justify-between select-none">
      {/* Workspace Switcher */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onSwitchWorkspace}
          className="flex items-center gap-2 px-2.5 py-1 rounded hover:bg-surface-100 transition-colors border border-surface-200 text-xs font-semibold text-surface-900 focus:outline-none focus:ring-1 focus:ring-surface-900 cursor-pointer"
          title="Switch workspace"
        >
          <Building2 className="h-3.5 w-3.5 text-surface-500" />
          <span>{workspaceName}</span>
          <ChevronDown className="h-3 w-3 text-surface-400 ml-1" />
        </button>

        {/* AI Status Indicator */}
        <div
          className={`flex items-center gap-1.5 ml-2 px-2 py-0.5 rounded border text-2xs font-medium ${
            isAiActive
              ? 'bg-blue-50/50 border-blue-200 text-blue-900'
              : 'bg-surface-50 border-surface-200 text-surface-500'
          }`}
        >
          <Sparkles className={`h-3 w-3 ${isAiActive ? 'text-blue-600' : 'text-surface-400'}`} />
          <span>{isAiActive ? 'AI Checks Active' : 'Rules-Only Mode (AI Disabled)'}</span>
        </div>
      </div>

      {/* User Info & Actions */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          {roles.map((r) => (
            <Badge key={r} size="sm" variant={r === 'admin' ? 'neutral' : 'info'}>
              {r.replace('_', ' ')}
            </Badge>
          ))}
        </div>

        <div className="text-xs text-surface-600 font-medium font-mono hidden sm:block">
          {email}
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={handleLogout}
          title="Sign out"
          leftIcon={<LogOut className="w-3.5 h-3.5" />}
        >
          <span className="hidden md:inline">Sign out</span>
        </Button>
      </div>
    </header>
  );
};