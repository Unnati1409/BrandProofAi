import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ContentSubmissionsPage } from '../Content/ContentSubmissionsPage';
import { ContentReviewWorkspace } from '../Content/ContentReviewWorkspace';
import { AuthProvider } from '../../context/AuthContext';
import { WorkspaceProvider } from '../../context/WorkspaceContext';

describe('Content Submissions and Review Workspace', () => {
  beforeEach(() => {
    localStorage.setItem('brandproof_token', 'mock-token');
    localStorage.setItem(
      'brandproof_user',
      JSON.stringify({
        id: 'user_reviewer',
        email: 'reviewer@aurahealth.demo',
        full_name: 'Marcus Vance',
        workspaces: [
          {
            workspace_id: 'ws_1',
            workspace_name: 'AuraHealth Global',
            workspace_slug: 'aurahealth',
            roles: ['reviewer'],
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
            id: 'user_reviewer',
            email: 'reviewer@aurahealth.demo',
            full_name: 'Marcus Vance',
            workspaces: [
              {
                workspace_id: 'ws_1',
                workspace_name: 'AuraHealth Global',
                workspace_slug: 'aurahealth',
                roles: ['reviewer'],
              },
            ],
          }),
        } as Response;
      }

      if (urlStr.endsWith('/content')) {
        return {
          ok: true,
          json: async () => [
            {
              id: 'cnt_01',
              workspace_id: 'ws_1',
              title: 'AuraCare Enterprise Press Release',
              file_type: 'txt',
              state: 'in_review',
              created_by: 'user_creator',
              current_version: 1,
              created_at: '2026-11-08T01:00:00Z',
              updated_at: '2026-11-08T01:10:00Z',
            },
          ],
        } as Response;
      }

      if (urlStr.includes('/content/cnt_01')) {
        return {
          ok: true,
          json: async () => ({
            item: {
              id: 'cnt_01',
              workspace_id: 'ws_1',
              title: 'AuraCare Enterprise Press Release',
              file_type: 'txt',
              state: 'in_review',
              created_by: 'user_creator',
              current_version: 1,
              created_at: '2026-11-08T01:00:00Z',
              updated_at: '2026-11-08T01:10:00Z',
            },
            versions: [
              {
                id: 'ver_01',
                content_id: 'cnt_01',
                workspace_id: 'ws_1',
                version_number: 1,
                raw_text: 'AuraHealth provides cheap healthcare services for clinics.',
                normalized_text: 'AuraHealth provides cheap healthcare services for clinics.',
                parsed_metadata: {},
                created_by: 'user_creator',
                created_at: '2026-11-08T01:00:00Z',
              },
            ],
            latest_findings: [
              {
                id: 'find_01',
                category: 'banned_term',
                severity: 'high',
                basis_label: 'rule_based',
                verdict: 'contradicted',
                accessibility_result: 'not_checked',
                target_text: 'cheap',
                start_offset: 24,
                end_offset: 29,
                explanation: "Usage of prohibited word 'cheap'.",
                suggestions: ['affordable', 'accessible'],
                decision: 'open',
              },
            ],
            comments: [],
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
              created_by: 'user_admin',
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

  it('renders content submissions page with active items', async () => {
    const onSelect = vi.fn();
    render(
      <AuthProvider>
        <WorkspaceProvider>
          <ContentSubmissionsPage onSelectContent={onSelect} />
        </WorkspaceProvider>
      </AuthProvider>
    );

    expect(screen.getByText('Marketing Content Submissions')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('AuraCare Enterprise Press Release')).toBeInTheDocument();
      expect(screen.getByText('Open Review')).toBeInTheDocument();
    });
  });

  it('renders review workspace with draft text, findings card, and actions', async () => {
    const onBack = vi.fn();
    render(
      <AuthProvider>
        <WorkspaceProvider>
          <ContentReviewWorkspace contentId="cnt_01" onBack={onBack} />
        </WorkspaceProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('AuraCare Enterprise Press Release')).toBeInTheDocument();
      expect(
        screen.getByText('AuraHealth provides cheap healthcare services for clinics.')
      ).toBeInTheDocument();
      expect(screen.getByText(/Usage of prohibited word 'cheap'/i)).toBeInTheDocument();
      expect(screen.getByText('Approve Content')).toBeInTheDocument();
    });
  });
});

