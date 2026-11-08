import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MembersPage } from '../Members/MembersPage';
import { AuthProvider } from '../../context/AuthContext';
import { WorkspaceProvider } from '../../context/WorkspaceContext';

describe('MembersPage', () => {
  beforeEach(() => {
    localStorage.setItem('brandproof_token', 'mock-token');
    localStorage.setItem(
      'brandproof_user',
      JSON.stringify({
        id: 'user_1',
        email: 'admin@aurahealth.demo',
        full_name: 'Dr. Sarah Chen',
        workspaces: [
          {
            workspace_id: 'ws_1',
            workspace_name: 'AuraHealth Technologies',
            workspace_slug: 'aurahealth',
            roles: ['admin', 'brand_owner'],
          },
        ],
      })
    );
    localStorage.setItem('brandproof_active_workspace_id', 'ws_1');

    // Mock fetch for auth & workspace details & members
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url: any) => {
      const urlStr = String(url);
      if (urlStr.includes('/api/v1/auth/me')) {
        return {
          ok: true,
          json: async () => ({
            id: 'user_1',
            email: 'admin@aurahealth.demo',
            full_name: 'Dr. Sarah Chen',
            workspaces: [
              {
                workspace_id: 'ws_1',
                workspace_name: 'AuraHealth Technologies',
                workspace_slug: 'aurahealth',
                roles: ['admin', 'brand_owner'],
              },
            ],
          }),
        } as Response;
      }

      if (urlStr.includes('/api/v1/workspaces/')) {
        if (urlStr.endsWith('/members')) {
          return {
            ok: true,
            json: async () => [
              {
                id: 'mem_1',
                workspace_id: 'ws_1',
                user_id: 'user_1',
                email: 'admin@aurahealth.demo',
                full_name: 'Dr. Sarah Chen',
                roles: ['admin', 'brand_owner'],
                created_at: '2026-11-01T10:00:00Z',
              },
              {
                id: 'mem_2',
                workspace_id: 'ws_1',
                user_id: 'user_2',
                email: 'creator@aurahealth.demo',
                full_name: 'Alex Rivera',
                roles: ['creator'],
                created_at: '2026-11-02T10:00:00Z',
              },
            ],
          } as Response;
        }

        return {
          ok: true,
          json: async () => [
            {
              id: 'ws_1',
              name: 'AuraHealth Technologies',
              slug: 'aurahealth',
              created_by: 'user_1',
              ai_enabled: true,
              retention_days: 90,
              created_at: '2026-11-01T10:00:00Z',
            },
          ],
        } as Response;
      }

      return {
        ok: true,
        json: async () => ({}),
      } as Response;
    });
  });

  it('renders separation of duties notice and members table', async () => {
    render(
      <AuthProvider>
        <WorkspaceProvider>
          <MembersPage />
        </WorkspaceProvider>
      </AuthProvider>
    );

    expect(screen.getByText('Members & Access Control')).toBeInTheDocument();
    expect(
      screen.getByText(/no user can approve content they created/i)
    ).toBeInTheDocument();

    // Check members list rendered from mock
    expect(await screen.findByText('Dr. Sarah Chen')).toBeInTheDocument();
    expect(await screen.findByText('Alex Rivera')).toBeInTheDocument();
    expect(screen.getByText('creator@aurahealth.demo')).toBeInTheDocument();
  });

  it('opens invite dialog when Invite Member button is clicked', async () => {
    render(
      <AuthProvider>
        <WorkspaceProvider>
          <MembersPage />
        </WorkspaceProvider>
      </AuthProvider>
    );

    const inviteBtn = await screen.findByRole('button', { name: /invite member/i });
    fireEvent.click(inviteBtn);

    expect(screen.getByText('Invite Workspace Member')).toBeInTheDocument();
    expect(screen.getByLabelText(/work email address/i)).toBeInTheDocument();
    expect(screen.getByText('Assigned Governance Roles')).toBeInTheDocument();
  });
});