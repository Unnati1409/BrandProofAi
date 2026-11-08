import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { RuleCataloguePage } from '../Rules/RuleCataloguePage';
import { AuthProvider } from '../../context/AuthContext';
import { WorkspaceProvider } from '../../context/WorkspaceContext';

describe('RuleCataloguePage', () => {
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

      if (urlStr.endsWith('/rules')) {
        return {
          ok: true,
          json: async () => [
            {
              id: 'rule_01',
              workspace_id: 'ws_1',
              rule_type: 'banned_term',
              severity: 'high',
              primary_term: 'cheap',
              secondary_term: 'affordable',
              payload: {
                banned_term: 'cheap',
                preferred_term: 'affordable',
              },
              explanation: "Do not use 'cheap'; use 'accessible' or 'affordable'.",
              status: 'candidate',
              created_at: '2026-11-08T01:00:00Z',
            },
          ],
        } as Response;
      }

      if (urlStr.endsWith('/facts')) {
        return {
          ok: true,
          json: async () => [
            {
              id: 'fact_01',
              workspace_id: 'ws_1',
              statement: 'AuraCare Enterprise pricing is $499/mo per clinic.',
              primary_reference: 'Section 4.1',
              source_owner: 'Finance Team',
              status: 'candidate',
              created_at: '2026-11-08T01:00:00Z',
            },
          ],
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

  it('renders brand rules catalogue with candidate items and confirm buttons', async () => {
    render(
      <AuthProvider>
        <WorkspaceProvider>
          <RuleCataloguePage />
        </WorkspaceProvider>
      </AuthProvider>
    );

    expect(screen.getByText('Brand Knowledge Catalogue')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText(/cheap/).length).toBeGreaterThan(0);
      expect(screen.getByText('Banned Term')).toBeInTheDocument();
      expect(screen.getByText('Candidate (Unconfirmed)')).toBeInTheDocument();
      expect(screen.getByText('Confirm')).toBeInTheDocument();
    });
  });
});

