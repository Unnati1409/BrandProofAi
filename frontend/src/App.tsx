import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { WorkspaceProvider, useWorkspace } from './context/WorkspaceContext';
import { LoginPage } from './pages/Auth/LoginPage';
import { RegisterPage } from './pages/Auth/RegisterPage';
import { WorkspaceSelectPage } from './pages/Workspaces/WorkspaceSelectPage';
import { AppShell } from './components/layout/AppShell';
import { DashboardOverview } from './pages/Dashboard/DashboardOverview';
import { GuidelinesPage } from './pages/Guidelines/GuidelinesPage';
import { RuleCataloguePage } from './pages/Rules/RuleCataloguePage';
import { ContentSubmissionsPage } from './pages/Content/ContentSubmissionsPage';
import { ContentReviewWorkspace } from './pages/Content/ContentReviewWorkspace';
import { MembersPage } from './pages/Members/MembersPage';
import { AccountSettingsPage } from './pages/Settings/AccountSettingsPage';
import { ShieldCheck, Loader2 } from 'lucide-react';

const MainAppContent: React.FC = () => {
  const { token, isLoading: isAuthLoading } = useAuth();
  const { activeWorkspace, isLoading: isWsLoading } = useWorkspace();
  const [authView, setAuthView] = useState<'login' | 'register'>('login');
  const [activeNav, setActiveNav] = useState('dashboard');
  const [isSwitchingWorkspace, setIsSwitchingWorkspace] = useState(false);
  const [selectedContentId, setSelectedContentId] = useState<string | null>(null);

  if (isAuthLoading) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-surface-50 text-surface-500">
        <Loader2 className="w-6 h-6 animate-spin mb-3 text-surface-700" />
        <p className="text-xs font-medium">Initializing BrandProof AI session...</p>
      </div>
    );
  }

  // 1. Unauthenticated -> Show Login or Register
  if (!token) {
    if (authView === 'register') {
      return (
        <RegisterPage
          onNavigateToLogin={() => setAuthView('login')}
          onRegisterSuccess={() => setAuthView('login')}
        />
      );
    }
    return (
      <LoginPage
        onNavigateToRegister={() => setAuthView('register')}
      />
    );
  }

  // 2. Authenticated, but no active workspace or currently choosing workspace
  if (!activeWorkspace || isSwitchingWorkspace) {
    if (isWsLoading && !isSwitchingWorkspace) {
      return (
        <div className="min-h-screen w-full flex flex-col items-center justify-center bg-surface-50 text-surface-500">
          <Loader2 className="w-6 h-6 animate-spin mb-3 text-surface-700" />
          <p className="text-xs font-medium">Loading workspace environment...</p>
        </div>
      );
    }

    return (
      <WorkspaceSelectPage
        onWorkspaceSelected={() => setIsSwitchingWorkspace(false)}
      />
    );
  }

  const handleNavSelect = (navId: string) => {
    setActiveNav(navId);
    setSelectedContentId(null);
  };

  // 3. Authenticated & Workspace Active -> Full Workspace AppShell
  return (
    <AppShell
      activeNav={activeNav}
      onNavSelect={handleNavSelect}
      onSwitchWorkspace={() => setIsSwitchingWorkspace(true)}
    >
      {activeNav === 'dashboard' && (
        selectedContentId ? (
          <ContentReviewWorkspace
            contentId={selectedContentId}
            onBack={() => setSelectedContentId(null)}
          />
        ) : (
          <DashboardOverview onSelectContent={(id) => setSelectedContentId(id)} />
        )
      )}

      {activeNav === 'guidelines' && <GuidelinesPage />}

      {activeNav === 'rules' && <RuleCataloguePage initialTab="rules" />}

      {activeNav === 'facts' && <RuleCataloguePage initialTab="facts" />}

      {(activeNav === 'content' || activeNav === 'review_queue') && (
        selectedContentId ? (
          <ContentReviewWorkspace
            contentId={selectedContentId}
            onBack={() => setSelectedContentId(null)}
          />
        ) : (
          <ContentSubmissionsPage
            onSelectContent={(id) => setSelectedContentId(id)}
          />
        )
      )}

      {activeNav === 'members' && <MembersPage />}

      {activeNav === 'settings' && <AccountSettingsPage />}

      {/* Audit or Fallback */}
      {!['dashboard', 'guidelines', 'rules', 'facts', 'content', 'review_queue', 'members', 'settings'].includes(
        activeNav
      ) && (
        <div className="bg-white border border-surface-200 rounded-lg p-10 text-center max-w-xl mx-auto my-12">
          <div className="w-10 h-10 rounded-full bg-surface-100 flex items-center justify-center mx-auto mb-3 text-surface-700">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <h2 className="text-sm font-bold text-surface-900 capitalize mb-1">
            {activeNav.replace('_', ' ')}
          </h2>
          <p className="text-xs text-surface-500 leading-relaxed mb-4">
            Viewing workspace governance module.
          </p>
          <div className="text-2xs font-mono text-surface-400 bg-surface-50 px-3 py-1.5 rounded inline-block border border-surface-200">
            Workspace: {activeWorkspace.name} ({activeWorkspace.slug})
          </div>
        </div>
      )}
    </AppShell>
  );
};

export function App() {
  return (
    <AuthProvider>
      <WorkspaceProvider>
        <MainAppContent />
      </WorkspaceProvider>
    </AuthProvider>
  );
}
export default App;
