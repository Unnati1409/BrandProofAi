import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
import { Workspace, WorkspaceMember, WorkspaceSettingsUpdate, UserRole } from '../types';
import { useAuth } from './AuthContext';
import { apiFetch } from '../lib/api';

interface WorkspaceContextType {
  workspaces: Workspace[];
  activeWorkspace: Workspace | null;
  members: WorkspaceMember[];
  currentUserRoles: UserRole[];
  isLoading: boolean;
  error: string | null;
  selectWorkspace: (workspaceId: string) => void;
  createWorkspace: (name: string, slug?: string) => Promise<Workspace>;
  updateWorkspaceSettings: (settings: WorkspaceSettingsUpdate) => Promise<Workspace>;
  refreshWorkspaces: () => Promise<void>;
  refreshMembers: () => Promise<void>;
  hasRole: (role: UserRole) => boolean;
  isAdmin: boolean;
  isBrandOwner: boolean;
  isManager: boolean;
  isReviewer: boolean;
  isCreator: boolean;
  canApprove: boolean;
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

export const WorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { token, user, refreshUser } = useAuth();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(() => {
    return localStorage.getItem('brandproof_active_workspace_id');
  });
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const authHeaders = useMemo(() => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    if (activeWorkspaceId) {
      headers['X-Workspace-ID'] = activeWorkspaceId;
    }
    return headers;
  }, [token, activeWorkspaceId]);

  const fetchWorkspaces = useCallback(async () => {
    if (!token) {
      setWorkspaces([]);
      setActiveWorkspace(null);
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const res = await apiFetch('/api/v1/workspaces/', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        throw new Error('Failed to fetch workspaces');
      }

      const data: Workspace[] = await res.json();
      setWorkspaces(data);

      if (data.length > 0) {
        const found = data.find((w) => w.id === activeWorkspaceId);
        if (found) {
          setActiveWorkspace(found);
        } else {
          setActiveWorkspace(data[0]);
          setActiveWorkspaceId(data[0].id);
          localStorage.setItem('brandproof_active_workspace_id', data[0].id);
        }
      } else {
        setActiveWorkspace(null);
        setActiveWorkspaceId(null);
        localStorage.removeItem('brandproof_active_workspace_id');
      }
    } catch (err: any) {
      setError(err.message || 'Error fetching workspaces');
    } finally {
      setIsLoading(false);
    }
  }, [token, activeWorkspaceId]);

  const fetchMembers = useCallback(async () => {
    if (!token || !activeWorkspaceId) {
      setMembers([]);
      return;
    }

    try {
      const res = await apiFetch(`/api/v1/workspaces/${activeWorkspaceId}/members`, {
        headers: authHeaders,
      });

      if (res.ok) {
        const data: WorkspaceMember[] = await res.json();
        setMembers(data);
      }
    } catch {
      // Silently fail if unauthorized or network error
    }
  }, [token, activeWorkspaceId, authHeaders]);

  useEffect(() => {
    fetchWorkspaces();
  }, [fetchWorkspaces]);

  useEffect(() => {
    if (activeWorkspaceId) {
      fetchMembers();
    } else {
      setMembers([]);
    }
  }, [activeWorkspaceId, fetchMembers]);

  const selectWorkspace = (workspaceId: string) => {
    const ws = workspaces.find((w) => w.id === workspaceId);
    if (ws) {
      setActiveWorkspaceId(ws.id);
      setActiveWorkspace(ws);
      localStorage.setItem('brandproof_active_workspace_id', ws.id);
    }
  };

  const createWorkspace = async (name: string, slug?: string): Promise<Workspace> => {
    if (!token) throw new Error('Not authenticated');

    const res = await apiFetch('/api/v1/workspaces/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ name, slug: slug || undefined }),
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData?.error?.message || 'Failed to create workspace');
    }

    const created: Workspace = await res.json();
    setWorkspaces((prev) => [...prev, created]);
    selectWorkspace(created.id);
    await refreshUser();
    return created;
  };

  const updateWorkspaceSettings = async (settings: WorkspaceSettingsUpdate): Promise<Workspace> => {
    if (!token || !activeWorkspaceId) throw new Error('No active workspace');

    const res = await apiFetch(`/api/v1/workspaces/${activeWorkspaceId}/settings`, {
      method: 'PATCH',
      headers: authHeaders,
      body: JSON.stringify(settings),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err?.error?.message || 'Failed to update workspace settings');
    }

    const updated: Workspace = await res.json();
    setActiveWorkspace(updated);
    setWorkspaces((prev) => prev.map((w) => (w.id === updated.id ? updated : w)));
    return updated;
  };

  // Derive roles for current user in active workspace
  const currentUserRoles = useMemo<UserRole[]>(() => {
    if (!user || !activeWorkspaceId) return [];
    
    // Check members list first
    const memberRecord = members.find((m) => m.user_id === user.id);
    if (memberRecord && memberRecord.roles) {
      return memberRecord.roles as UserRole[];
    }

    // Fall back to user profile workspaces
    const wsEntry = user.workspaces?.find((w) => w.workspace_id === activeWorkspaceId);
    return (wsEntry?.roles || []) as UserRole[];
  }, [user, activeWorkspaceId, members]);

  const hasRole = useCallback((role: UserRole) => currentUserRoles.includes(role), [currentUserRoles]);
  const isAdmin = useMemo(() => currentUserRoles.includes('admin'), [currentUserRoles]);
  const isBrandOwner = useMemo(() => currentUserRoles.includes('brand_owner'), [currentUserRoles]);
  const isManager = useMemo(() => currentUserRoles.includes('manager'), [currentUserRoles]);
  const isReviewer = useMemo(() => currentUserRoles.includes('reviewer'), [currentUserRoles]);
  const isCreator = useMemo(() => currentUserRoles.includes('creator'), [currentUserRoles]);
  const canApprove = useMemo(() => isReviewer || isManager, [isReviewer, isManager]);

  return (
    <WorkspaceContext.Provider
      value={{
        workspaces,
        activeWorkspace,
        members,
        currentUserRoles,
        isLoading,
        error,
        selectWorkspace,
        createWorkspace,
        updateWorkspaceSettings,
        refreshWorkspaces: fetchWorkspaces,
        refreshMembers: fetchMembers,
        hasRole,
        isAdmin,
        isBrandOwner,
        isManager,
        isReviewer,
        isCreator,
        canApprove,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
};

export const useWorkspace = (): WorkspaceContextType => {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error('useWorkspace must be used within a WorkspaceProvider');
  }
  return context;
};
