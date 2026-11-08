import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { GuidelinesPage } from '../Guidelines/GuidelinesPage';
import { AuthProvider } from '../../context/AuthContext';
import { WorkspaceProvider } from '../../context/WorkspaceContext';

describe('GuidelinesPage', () => {
  beforeEach(() => {
    localStorage.setItem('brandproof_token', 'mock-token');
    localStorage.setItem(
      'brandproof_user',
      JSON.stringify({
        id: 'user_bo',
        email: 'brandowner@aurahealth.demo',
        full_name: 'Elena Rostova',
        workspaces: [
          {
            workspace_id: 'ws_1',
            workspace_name: 'AuraHealth Global',
            workspace_slug: 'aurahealth',
            roles: ['brand_owner'],
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
            id: 'user_bo',
            email: 'brandowner@aurahealth.demo',
            full_name: 'Elena Rostova',
            workspaces: [
              {
                workspace_id: 'ws_1',
                workspace_name: 'AuraHealth Global',
                workspace_slug: 'aurahealth',
                roles: ['brand_owner'],
              },
            ],
          }),
        } as Response;
      }

      if (urlStr.endsWith('/sources')) {
        return {
          ok: true,
          json: async () => ({
            items: [
              {
                id: 'src_01',
                workspace_id: 'ws_1',
                filename: 'AuraHealth_Brand_Guidelines_2026.pdf',
                file_type: 'pdf',
                storage_path: 'ws_1/guidelines/src_01/AuraHealth_Brand_Guidelines_2026.pdf',
                file_size_bytes: 2048576,
                status: 'uploaded',
                error_message: null,
                uploaded_by: 'user_bo',
                created_at: '2026-11-08T01:00:00Z',
                is_approved: false,
              },
            ],
            total: 1,
          }),
        } as Response;
      }

      if (urlStr.includes('/api/v1/workspaces')) {
        return {
          ok: true,
          json: async () => [
            {
              id: 'ws_1',
              name: 'AuraHealth Global',
              slug: 'aurahealth',
              created_by: 'user_bo',
              ai_enabled: false,
              retention_days: 90,
              created_at: '2026-11-05T00:00:00Z',
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

  it('renders guideline source management header and governance alert banner', async () => {
    render(
      <AuthProvider>
        <WorkspaceProvider>
          <GuidelinesPage />
        </WorkspaceProvider>
      </AuthProvider>
    );

    expect(screen.getByText('Guideline Source Management')).toBeInTheDocument();
    expect(
      screen.getByText('Approval Invariant: Raw Documents Are Candidate Evidence')
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('AuraHealth_Brand_Guidelines_2026.pdf')).toBeInTheDocument();
      expect(screen.getByText('Unapproved Candidate')).toBeInTheDocument();
      expect(screen.getByText('Upload Guideline')).toBeInTheDocument();
    });
  });

  it('displays empty state when no documents have been uploaded', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url: any) => {
      const urlStr = String(url);
      if (urlStr.includes('/api/v1/auth/me')) {
        return {
          ok: true,
          json: async () => ({
            id: 'user_bo',
            email: 'brandowner@aurahealth.demo',
            full_name: 'Elena Rostova',
            workspaces: [
              {
                workspace_id: 'ws_1',
                workspace_name: 'AuraHealth Global',
                workspace_slug: 'aurahealth',
                roles: ['brand_owner'],
              },
            ],
          }),
        } as Response;
      }

      if (urlStr.includes('/api/v1/workspaces') && !urlStr.endsWith('/sources')) {
        return {
          ok: true,
          json: async () => [
            {
              id: 'ws_1',
              name: 'AuraHealth Global',
              slug: 'aurahealth',
              created_by: 'user_bo',
              ai_enabled: false,
              retention_days: 90,
              created_at: '2026-11-05T00:00:00Z',
            },
          ],
        } as Response;
      }

      if (urlStr.endsWith('/sources')) {
        return {
          ok: true,
          json: async () => ({ items: [], total: 0 }),
        } as Response;
      }

      return {
        ok: true,
        json: async () => ({}),
      } as Response;
    });

    render(
      <AuthProvider>
        <WorkspaceProvider>
          <GuidelinesPage />
        </WorkspaceProvider>
      </AuthProvider>
    );

    await waitFor(
      () => {
        expect(screen.getByText('No guideline documents imported')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });
});
