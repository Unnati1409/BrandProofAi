import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useWorkspace } from '../../context/WorkspaceContext';
import { Button, Input, Dialog, Badge } from '../../components/ui';
import { Building2, Plus, ArrowRight, LogOut, ShieldCheck, Sparkles } from 'lucide-react';

interface WorkspaceSelectPageProps {
  onWorkspaceSelected?: () => void;
}

export const WorkspaceSelectPage: React.FC<WorkspaceSelectPageProps> = ({
  onWorkspaceSelected,
}) => {
  const { user, logout } = useAuth();
  const { workspaces, selectWorkspace, createWorkspace, isLoading } = useWorkspace();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [newWorkspaceSlug, setNewWorkspaceSlug] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const handleSelect = (workspaceId: string) => {
    selectWorkspace(workspaceId);
    onWorkspaceSelected?.();
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWorkspaceName.trim()) {
      setCreateError('Workspace name is required');
      return;
    }

    setIsCreating(true);
    setCreateError(null);

    try {
      const created = await createWorkspace(
        newWorkspaceName.trim(),
        newWorkspaceSlug.trim() || undefined
      );
      setIsCreateOpen(false);
      setNewWorkspaceName('');
      setNewWorkspaceSlug('');
      selectWorkspace(created.id);
      onWorkspaceSelected?.();
    } catch (err: any) {
      setCreateError(err.message || 'Failed to create workspace');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-surface-50 flex flex-col">
      {/* Top Header */}
      <header className="h-14 border-b border-surface-200 bg-white px-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded bg-surface-900 text-white flex items-center justify-center">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <span className="font-bold text-sm tracking-tight text-surface-900">
            BrandProof AI
          </span>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-xs font-semibold text-surface-900">{user?.full_name}</div>
            <div className="text-2xs text-surface-500 font-mono">{user?.email}</div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={logout}
            leftIcon={<LogOut className="w-3.5 h-3.5" />}
          >
            Sign out
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-4xl w-full mx-auto p-6 md:p-10 flex flex-col justify-center">
        <div className="mb-8 flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-surface-900">
              Workspaces
            </h1>
            <p className="text-xs text-surface-500 mt-1">
              Select an enterprise workspace to manage guidelines, review content, and verify compliance.
            </p>
          </div>

          <Button
            variant="primary"
            onClick={() => setIsCreateOpen(true)}
            leftIcon={<Plus className="w-4 h-4" />}
          >
            Create Workspace
          </Button>
        </div>

        {/* Workspaces List / Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[1, 2].map((i) => (
              <div
                key={i}
                className="h-32 bg-white rounded-lg border border-surface-200 p-5 animate-pulse"
              />
            ))}
          </div>
        ) : workspaces.length === 0 ? (
          <div className="bg-white border border-surface-200 rounded-lg p-10 text-center flex flex-col items-center">
            <div className="w-12 h-12 rounded-full bg-surface-100 flex items-center justify-center text-surface-500 mb-3">
              <Building2 className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-semibold text-surface-900 mb-1">
              No Workspaces Found
            </h3>
            <p className="text-xs text-surface-500 max-w-sm mb-5">
              You are not a member of any workspace yet. Create a new workspace to get started.
            </p>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsCreateOpen(true)}
              leftIcon={<Plus className="w-3.5 h-3.5" />}
            >
              Create Workspace
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {workspaces.map((ws) => {
              const userMembership = user?.workspaces?.find((w) => w.workspace_id === ws.id);
              const roles = userMembership?.roles || [];

              return (
                <div
                  key={ws.id}
                  className="bg-white border border-surface-200 rounded-lg p-5 shadow-subtle hover:border-surface-400 transition-colors flex flex-col justify-between group"
                >
                  <div>
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="flex items-center gap-2.5">
                        <div className="w-9 h-9 rounded bg-surface-100 border border-surface-200 flex items-center justify-center text-surface-700 font-bold text-xs uppercase">
                          {ws.name.slice(0, 2)}
                        </div>
                        <div>
                          <h2 className="text-sm font-bold text-surface-900 group-hover:text-surface-950 transition-colors">
                            {ws.name}
                          </h2>
                          <div className="text-2xs font-mono text-surface-500">
                            /{ws.slug}
                          </div>
                        </div>
                      </div>

                      {ws.ai_enabled ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-2xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <Sparkles className="w-2.5 h-2.5" />
                          AI Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-2xs font-medium bg-surface-100 text-surface-600 border border-surface-200">
                          AI Inactive
                        </span>
                      )}
                    </div>

                    <div className="mt-3 flex flex-wrap gap-1">
                      {roles.map((role) => (
                        <Badge key={role} size="sm" variant="neutral">
                          {role.replace('_', ' ')}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div className="mt-5 pt-3 border-t border-surface-100 flex items-center justify-between">
                    <span className="text-2xs text-surface-400 font-mono">
                      Retention: {ws.retention_days}d
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleSelect(ws.id)}
                      rightIcon={<ArrowRight className="w-3 h-3" />}
                    >
                      Enter Workspace
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Create Workspace Modal */}
      <Dialog
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Create New Workspace"
        description="A workspace contains members, brand guidelines, approved facts, assets and content."
        footer={
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsCreateOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              isLoading={isCreating}
              onClick={handleCreate}
            >
              Create Workspace
            </Button>
          </div>
        }
      >
        <form onSubmit={handleCreate} className="space-y-4 py-2">
          {createError && (
            <div className="p-2.5 rounded bg-red-50 border border-red-200 text-red-800 text-xs">
              {createError}
            </div>
          )}

          <Input
            label="Workspace Name"
            placeholder="e.g. AuraHealth Technologies"
            value={newWorkspaceName}
            onChange={(e) => {
              setNewWorkspaceName(e.target.value);
              if (!newWorkspaceSlug) {
                setNewWorkspaceSlug(
                  e.target.value
                    .toLowerCase()
                    .replace(/[^a-z0-9]/g, '-')
                    .replace(/-+/g, '-')
                    .slice(0, 30)
                );
              }
            }}
            required
            helperText="The official name of the organization or brand."
          />

          <Input
            label="URL Slug (Optional)"
            placeholder="aurahealth"
            value={newWorkspaceSlug}
            onChange={(e) => setNewWorkspaceSlug(e.target.value)}
            helperText="Used in identifiers and route scoping."
            isMonospace
          />
        </form>
      </Dialog>
    </div>
  );
};