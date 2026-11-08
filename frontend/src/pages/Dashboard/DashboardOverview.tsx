import React, { useState, useEffect, useCallback } from 'react';
import { useWorkspace } from '../../context/WorkspaceContext';
import { apiFetch } from '../../lib/api';
import { ContentItem } from '../../types';
import {
  Button,
  PageHeader,
  Table,
  Badge,
  SeverityBadge,
  BasisLabel,
  VerdictBadge,
  EvidenceBlock,
  DiffView,
  Dialog,
  Toast,
  ToastItem,
} from '../../components/ui';
import { Plus, ShieldCheck, FileText, Loader2 } from 'lucide-react';

interface ContentRecord {
  id: string;
  title: string;
  version: string;
  author: string;
  state: 'draft' | 'checked' | 'in_review' | 'changes_requested' | 'approved' | 'archived';
  highFindings: number;
  updatedAt: string;
}

export const DashboardOverview: React.FC<{
  onSelectContent?: (id: string) => void;
}> = ({ onSelectContent }) => {
  const { activeWorkspace, isCreator } = useWorkspace();
  const [isSubmitOpen, setIsSubmitOpen] = useState(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [items, setItems] = useState<ContentItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchItems = useCallback(async () => {
    if (!activeWorkspace) return;
    setIsLoading(true);
    try {
      const res = await apiFetch(`/api/v1/workspaces/${activeWorkspace.id}/content`);
      if (res.ok) {
        const data = await res.json();
        setItems(data || []);
      }
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  }, [activeWorkspace]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  const records: ContentRecord[] = items.length > 0 ? items.map((item) => ({
    id: item.id,
    title: item.title,
    version: `v${item.current_version}`,
    author: item.created_by ? item.created_by.slice(0, 8) : 'Creator',
    state: item.state as ContentRecord['state'],
    highFindings: 0,
    updatedAt: new Date(item.updated_at || item.created_at).toLocaleString(),
  })) : [];

  const columns = [
    {
      key: 'title',
      header: 'Submission Title',
      render: (item: ContentRecord) => (
        <div
          className={`flex flex-col ${onSelectContent ? 'cursor-pointer hover:underline text-primary-600' : ''}`}
          onClick={() => onSelectContent?.(item.id)}
        >
          <span className="font-semibold text-surface-900">{item.title}</span>
          <span className="font-mono text-2xs text-surface-400">{item.id}</span>
        </div>
      ),
    },
    {
      key: 'version',
      header: 'Version',
      width: '80px',
      render: (item: ContentRecord) => (
        <span className="font-mono text-xs text-surface-600">{item.version}</span>
      ),
    },
    {
      key: 'author',
      header: 'Author',
      render: (item: ContentRecord) => (
        <span className="text-xs text-surface-700">{item.author}</span>
      ),
    },
    {
      key: 'state',
      header: 'State',
      width: '120px',
      render: (item: ContentRecord) => {
        const stateConfig: Record<string, React.ReactNode> = {
          draft: <Badge variant="neutral">Draft</Badge>,
          checked: <Badge variant="warning">Checked</Badge>,
          in_review: <Badge variant="info">In Review</Badge>,
          changes_requested: <Badge variant="warning">Changes Requested</Badge>,
          approved: <Badge variant="success">Cleared for Publication</Badge>,
          archived: <Badge variant="neutral">Archived</Badge>,
        };
        return stateConfig[item.state] || <Badge variant="neutral">{item.state}</Badge>;
      },
    },
    {
      key: 'highFindings',
      header: 'Open High Findings',
      isNumeric: true,
      width: '140px',
      render: (item: ContentRecord) => (
        item.highFindings > 0 ? (
          <span className="text-xs font-semibold text-red-600">
            {item.highFindings} Blocker{item.highFindings > 1 ? 's' : ''}
          </span>
        ) : (
          <span className="text-xs text-surface-400">0</span>
        )
      ),
    },
    {
      key: 'updatedAt',
      header: 'Last Updated',
      align: 'right' as const,
      isNumeric: true,
      width: '140px',
      render: (item: ContentRecord) => (
        <span className="text-xs text-surface-500 font-mono">{item.updatedAt}</span>
      ),
    },
  ];

  const handleSimulateCheck = () => {
    setToasts((prev) => [
      ...prev,
      {
        id: String(Date.now()),
        type: 'success',
        message: 'Review run completed successfully. 2 rule-based findings and 1 advisory claim finding identified.',
      },
    ]);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Brand Compliance Workspace"
        description="Pre-publication editorial governance, claim verification, and accessibility clearance."
        badge={
          <Badge variant="info">
            <ShieldCheck className="h-3 w-3 inline mr-1" /> Active Guard
          </Badge>
        }
        actions={
          isCreator ? (
            <Button
              variant="primary"
              leftIcon={<Plus className="h-3.5 w-3.5" />}
              onClick={() => setIsSubmitOpen(true)}
            >
              New Submission
            </Button>
          ) : undefined
        }
      />

      {/* Submissions Table */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-surface-900">
            Active Submissions & Governance Queue
          </h2>
          <Button variant="outline" size="sm" onClick={handleSimulateCheck}>
            Trigger Sample Check Run
          </Button>
        </div>
        {isLoading ? (
          <div className="flex items-center justify-center p-8 bg-white border border-surface-200 rounded-md">
            <Loader2 className="h-5 w-5 animate-spin text-surface-500 mr-2" />
            <span className="text-xs text-surface-500">Loading active submissions...</span>
          </div>
        ) : (
          <Table
            columns={columns}
            data={records}
            keyExtractor={(r) => r.id}
          />
        )}
      </div>

      {/* Showcase of Grounded Evidence & Validation Components */}
      <div className="space-y-3 pt-4 border-t border-surface-200">
        <h2 className="text-base font-semibold text-surface-900">
          Component Standard: Sourced Finding & Evidence Block Preview
        </h2>
        <div className="p-4 bg-white border border-surface-200 rounded-md shadow-subtle space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity="high" />
            <BasisLabel basis="ai_assisted" />
            <VerdictBadge verdict="contradicted" />
            <span className="text-xs text-surface-500 ml-auto">
              Triage Indicator: <strong>High</strong> (Triage Aid Only)
            </span>
          </div>

          <p className="text-xs text-surface-700 leading-relaxed">
            <strong>Finding Explanation:</strong> The submitted press release states an enterprise subscription price of <strong>$449/mo</strong>, which directly contradicts the approved 2026 pricing schedule of <strong>$499/mo</strong> per clinic.
          </p>

          <EvidenceBlock
            quotedContent="AuraCare Enterprise is available immediately across all clinical networks for only $449/month."
            quotedApprovedSource="AuraCare Enterprise 2026 standard pricing is fixed at $499/month per clinic, billed annually."
            sourceReference="2026 Pricing Schedule §4.1"
            sourceDocumentName="AuraHealth_Brand_and_Commercial_Guidelines_2026.pdf"
            ruleOrFactId="fact_price_2026_01"
            owner="Finance & Product Marketing"
          />

          <DiffView
            originalText="AuraCare Enterprise is available immediately across all clinical networks for only $449/month."
            suggestedText="AuraCare Enterprise is available immediately across all clinical networks for $499/month per clinic."
          />
        </div>
      </div>

      {/* Submission Dialog */}
      <Dialog
        isOpen={isSubmitOpen}
        onClose={() => setIsSubmitOpen(false)}
        title="Submit New Content for Review"
        description="Upload DOCX or paste plain text for deterministic and grounded claim validation."
        footer={
          <>
            <Button variant="ghost" onClick={() => setIsSubmitOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                setIsSubmitOpen(false);
                setToasts((prev) => [
                  ...prev,
                  {
                    id: String(Date.now()),
                    type: 'success',
                    message: 'Draft content created as Version 1. Review run queued.',
                  },
                ]);
              }}
            >
              Submit Version 1
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div className="p-3 bg-surface-50 border border-surface-200 rounded text-xs text-surface-600 flex items-center gap-2">
            <FileText className="h-4 w-4 text-surface-500" />
            <span>Supported formats: Plain Text, Word (.docx), or PDF. Maximum file size: 10MB.</span>
          </div>
          <p className="text-xs text-surface-500">
            Upon submission, the automated review pipeline will evaluate terminology, required wording, banned terms, heading structure, and verify claims against confirmed workspace sources.
          </p>
        </div>
      </Dialog>

      <Toast toasts={toasts} onDismiss={(id) => setToasts((prev) => prev.filter((t) => t.id !== id))} />
    </div>
  );
};
