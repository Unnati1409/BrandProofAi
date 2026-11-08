import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useWorkspace } from '../../context/WorkspaceContext';
import {
  Button,
  Input,
  Dialog,
  Badge,
  PageHeader,
  Checkbox,
} from '../../components/ui';
import { UserRole, WorkspaceMember } from '../../types';
import { apiFetch } from '../../lib/api';
import {
  UserPlus,
  Trash2,
  Edit2,
  AlertCircle,
  Info,
} from 'lucide-react';

interface RoleOption {
  role: UserRole;
  label: string;
  description: string;
}

const AVAILABLE_ROLES: RoleOption[] = [
  {
    role: 'admin',
    label: 'Admin',
    description: 'Workspace configuration, member access, audit logs, and external AI disclosure approval.',
  },
  {
    role: 'brand_owner',
    label: 'Brand Owner',
    description: 'Maintains knowledge base, ingests guidelines, and confirms or rejects candidate rules and facts.',
  },
  {
    role: 'manager',
    label: 'Manager',
    description: 'Grants final publication approvals and manages content archiving.',
  },
  {
    role: 'reviewer',
    label: 'Reviewer',
    description: 'Conducts editorial reviews, requests changes, and approves content they did not create.',
  },
  {
    role: 'creator',
    label: 'Creator',
    description: 'Submits drafts, triages pipeline findings, and applies or dismisses suggestions with written justification.',
  },
];

export const MembersPage: React.FC = () => {
  const { user } = useAuth();
  const { activeWorkspace, members, refreshMembers, isAdmin } = useWorkspace();

  // Dialog states
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRoles, setInviteRoles] = useState<UserRole[]>(['creator']);
  const [isInviting, setIsInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);

  // Edit Roles state
  const [editingMember, setEditingMember] = useState<WorkspaceMember | null>(null);
  const [editRoles, setEditRoles] = useState<UserRole[]>([]);
  const [isUpdatingRoles, setIsUpdatingRoles] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  // Remove confirmation state
  const [removingMember, setRemovingMember] = useState<WorkspaceMember | null>(null);
  const [isRemoving, setIsRemoving] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);

  const getRoleBadgeVariant = (role: UserRole): 'neutral' | 'info' | 'success' | 'warning' | 'error' => {
    switch (role) {
      case 'admin':
        return 'neutral';
      case 'brand_owner':
        return 'info';
      case 'manager':
        return 'warning';
      case 'reviewer':
        return 'info';
      case 'creator':
        return 'success';
      default:
        return 'neutral';
    }
  };

  const handleOpenInvite = () => {
    setInviteEmail('');
    setInviteRoles(['creator']);
    setInviteError(null);
    setIsInviteOpen(true);
  };

  const toggleInviteRole = (role: UserRole) => {
    setInviteRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
    );
  };

  const handleInviteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) {
      setInviteError('Work email is required.');
      return;
    }
    if (inviteRoles.length === 0) {
      setInviteError('At least one role must be assigned.');
      return;
    }

    setIsInviting(true);
    setInviteError(null);

    try {
      const res = await apiFetch(
        `/api/v1/workspaces/${activeWorkspace?.id}/members/invite`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            email: inviteEmail.trim(),
            roles: inviteRoles,
          }),
        }
      );

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.error?.message || 'Failed to invite member.');
      }

      await refreshMembers();
      setIsInviteOpen(false);
    } catch (err: any) {
      setInviteError(err.message || 'An error occurred while inviting member.');
    } finally {
      setIsInviting(false);
    }
  };

  const handleOpenEdit = (member: WorkspaceMember) => {
    setEditingMember(member);
    setEditRoles(member.roles);
    setEditError(null);
  };

  const toggleEditRole = (role: UserRole) => {
    setEditRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
    );
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingMember || !activeWorkspace) return;
    if (editRoles.length === 0) {
      setEditError('Member must have at least one assigned role.');
      return;
    }

    setIsUpdatingRoles(true);
    setEditError(null);

    try {
      const res = await apiFetch(
        `/api/v1/workspaces/${activeWorkspace.id}/members/${editingMember.user_id}`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ roles: editRoles }),
        }
      );

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.error?.message || 'Failed to update member roles.');
      }

      await refreshMembers();
      setEditingMember(null);
    } catch (err: any) {
      setEditError(err.message || 'An error occurred while updating roles.');
    } finally {
      setIsUpdatingRoles(false);
    }
  };

  const handleRemoveSubmit = async () => {
    if (!removingMember || !activeWorkspace) return;

    setIsRemoving(true);
    setRemoveError(null);

    try {
      const res = await apiFetch(
        `/api/v1/workspaces/${activeWorkspace.id}/members/${removingMember.user_id}`,
        {
          method: 'DELETE',
        }
      );

      if (!res.ok && res.status !== 204) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.error?.message || 'Failed to remove member.');
      }

      await refreshMembers();
      setRemovingMember(null);
    } catch (err: any) {
      setRemoveError(err.message || 'An error occurred while removing member.');
    } finally {
      setIsRemoving(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Members & Access Control"
        description={`Manage permissions and role assignments for ${activeWorkspace?.name || 'this workspace'}.`}
        actions={
          isAdmin ? (
            <Button
              variant="primary"
              size="sm"
              leftIcon={<UserPlus className="w-3.5 h-3.5" />}
              onClick={handleOpenInvite}
            >
              Invite Member
            </Button>
          ) : undefined
        }
      />

      {/* Role Principle Notice */}
      <div className="p-3.5 rounded-lg bg-surface-50 border border-surface-200 text-xs text-surface-700 flex items-start gap-3">
        <Info className="w-4 h-4 shrink-0 text-surface-500 mt-0.5" />
        <div className="space-y-1">
          <p className="font-semibold text-surface-900">
            Strict Separation of Duties
          </p>
          <p className="text-surface-600 leading-relaxed">
            Users may hold multiple roles. However, <strong>no user can approve content they created</strong>.
            This requirement is strictly enforced server-side via both API authorization guards and a database trigger constraint.
          </p>
        </div>
      </div>

      {/* Members Table */}
      <div className="bg-white border border-surface-200 rounded-lg overflow-hidden shadow-subtle">
        <div className="px-5 py-3 border-b border-surface-200 bg-surface-50 flex items-center justify-between">
          <span className="text-xs font-semibold text-surface-700 uppercase tracking-wider">
            Active Members ({members.length})
          </span>
          {!isAdmin && (
            <span className="text-2xs text-surface-500 italic">
              Read-only view (Admin role required to manage members)
            </span>
          )}
        </div>

        <div className="divide-y divide-surface-100">
          {members.map((m) => {
            const isSelf = m.user_id === user?.id;

            return (
              <div
                key={m.id}
                className="px-5 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-surface-50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-surface-900 text-white flex items-center justify-center font-bold text-xs">
                    {m.full_name?.charAt(0) || m.email.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-surface-900">
                        {m.full_name}
                      </span>
                      {isSelf && (
                        <span className="px-1.5 py-0.2 rounded text-2xs bg-surface-200 text-surface-800 font-medium">
                          You
                        </span>
                      )}
                    </div>
                    <div className="text-2xs font-mono text-surface-500">
                      {m.email}
                    </div>
                  </div>
                </div>

                <div className="flex items-center flex-wrap gap-1.5 sm:justify-center">
                  {m.roles.map((role) => (
                    <Badge
                      key={role}
                      size="sm"
                      variant={getRoleBadgeVariant(role)}
                    >
                      {role.replace('_', ' ')}
                    </Badge>
                  ))}
                </div>

                <div className="flex items-center justify-end gap-2 text-xs">
                  <span className="text-2xs text-surface-400 font-mono hidden md:inline">
                    Joined {new Date(m.created_at).toLocaleDateString()}
                  </span>

                  {isAdmin && (
                    <div className="flex items-center gap-1.5 ml-3">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleOpenEdit(m)}
                        title="Edit Roles"
                        leftIcon={<Edit2 className="w-3 h-3" />}
                      >
                        Edit
                      </Button>
                      {!isSelf && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setRemovingMember(m)}
                          title="Remove Member"
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Invite Member Dialog */}
      <Dialog
        isOpen={isInviteOpen}
        onClose={() => setIsInviteOpen(false)}
        title="Invite Workspace Member"
        description="Add a colleague and assign governance roles to their profile."
        footer={
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsInviteOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              isLoading={isInviting}
              onClick={handleInviteSubmit}
            >
              Send Invitation
            </Button>
          </div>
        }
      >
        <form onSubmit={handleInviteSubmit} className="space-y-4 py-2">
          {inviteError && (
            <div className="p-2.5 rounded bg-red-50 border border-red-200 text-red-800 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{inviteError}</span>
            </div>
          )}

          <Input
            label="Work Email Address"
            type="email"
            placeholder="colleague@aurahealth.demo"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            required
            helperText="The user will receive access under this email address."
          />

          <div>
            <label className="text-xs font-semibold text-surface-700 block mb-2">
              Assigned Governance Roles
            </label>
            <div className="space-y-2.5 bg-surface-50 p-3 rounded border border-surface-200">
              {AVAILABLE_ROLES.map(({ role, label, description }) => (
                <div
                  key={role}
                  className="flex items-start gap-2.5 p-1 rounded hover:bg-white transition-colors cursor-pointer"
                  onClick={() => toggleInviteRole(role)}
                >
                  <Checkbox
                    checked={inviteRoles.includes(role)}
                    onChange={() => toggleInviteRole(role)}
                    className="mt-0.5"
                  />
                  <div>
                    <div className="text-xs font-bold text-surface-900">
                      {label}
                    </div>
                    <div className="text-2xs text-surface-500">
                      {description}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </form>
      </Dialog>

      {/* Edit Roles Dialog */}
      <Dialog
        isOpen={!!editingMember}
        onClose={() => setEditingMember(null)}
        title={`Edit Roles for ${editingMember?.full_name}`}
        description={`Configure permissions for ${editingMember?.email}.`}
        footer={
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setEditingMember(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              isLoading={isUpdatingRoles}
              onClick={handleEditSubmit}
            >
              Save Changes
            </Button>
          </div>
        }
      >
        <form onSubmit={handleEditSubmit} className="space-y-4 py-2">
          {editError && (
            <div className="p-2.5 rounded bg-red-50 border border-red-200 text-red-800 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{editError}</span>
            </div>
          )}

          <div className="space-y-2.5 bg-surface-50 p-3 rounded border border-surface-200">
            {AVAILABLE_ROLES.map(({ role, label, description }) => (
              <div
                key={role}
                className="flex items-start gap-2.5 p-1 rounded hover:bg-white transition-colors cursor-pointer"
                onClick={() => toggleEditRole(role)}
              >
                <Checkbox
                  checked={editRoles.includes(role)}
                  onChange={() => toggleEditRole(role)}
                  className="mt-0.5"
                />
                <div>
                  <div className="text-xs font-bold text-surface-900">{label}</div>
                  <div className="text-2xs text-surface-500">{description}</div>
                </div>
              </div>
            ))}
          </div>
        </form>
      </Dialog>

      {/* Remove Member Confirmation Dialog */}
      <Dialog
        isOpen={!!removingMember}
        onClose={() => setRemovingMember(null)}
        title="Remove Member from Workspace"
        description="Are you sure you want to remove this member? They will lose all access to workspace guidelines, facts, and content."
        footer={
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setRemovingMember(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              isLoading={isRemoving}
              onClick={handleRemoveSubmit}
            >
              Remove Member
            </Button>
          </div>
        }
      >
        <div className="py-2">
          {removeError && (
            <div className="p-2.5 mb-3 rounded bg-red-50 border border-red-200 text-red-800 text-xs">
              {removeError}
            </div>
          )}
          <p className="text-xs text-surface-700">
            Removing <span className="font-semibold text-surface-900">{removingMember?.full_name}</span> ({removingMember?.email}).
          </p>
        </div>
      </Dialog>
    </div>
  );
};