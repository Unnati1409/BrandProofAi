import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AccountSettingsPage } from '../Settings/AccountSettingsPage';
import { AuthProvider } from '../../context/AuthContext';
import { WorkspaceProvider } from '../../context/WorkspaceContext';

describe('AccountSettingsPage', () => {
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
            roles: ['admin'],
          },
        ],
      })
    );
    localStorage.setItem('brandproof_active_workspace_id', 'ws_1');

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
                roles: ['admin'],
              },
            ],
          }),
        } as Response;
      }

      if (urlStr.includes('/api/v1/workspaces/')) {
        return {
          ok: true,
          json: async () => [
            {
              id: 'ws_1',
              name: 'AuraHealth Technologies',
              slug: 'aurahealth',
              created_by: 'user_1',
              ai_enabled: true,
              ai_enabled_at: '2026-11-01T10:00:00Z',
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

  it('renders profile, workspace retention and external AI disclosure', async () => {
    render(
      <AuthProvider>
        <WorkspaceProvider>
          <AccountSettingsPage />
        </WorkspaceProvider>
      </AuthProvider>
    );

    expect(screen.getByText('Settings & Governance')).toBeInTheDocument();
    expect(screen.getByText('Your Profile')).toBeInTheDocument();
    expect(screen.getByText('Dr. Sarah Chen')).toBeInTheDocument();
    expect(screen.getByText('admin@aurahealth.demo')).toBeInTheDocument();

    // AI Disclosure principles
    expect(
      screen.getByText(/Google Gemini External AI Disclosure & Controls/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Approved Sources Only:/i)).toBeInTheDocument();
    expect(screen.getByText(/Deterministic Fallback:/i)).toBeInTheDocument();
  });
});