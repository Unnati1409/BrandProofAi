import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export interface AppShellProps {
  activeNav: string;
  onNavSelect: (id: string) => void;
  onSwitchWorkspace?: () => void;
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({
  activeNav,
  onNavSelect,
  onSwitchWorkspace,
  children,
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-surface-50">
      <Sidebar
        activeNav={activeNav}
        onNavSelect={onNavSelect}
        isCollapsed={isCollapsed}
        onToggleCollapse={() => setIsCollapsed(!isCollapsed)}
      />
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        <TopBar onSwitchWorkspace={onSwitchWorkspace} />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
};