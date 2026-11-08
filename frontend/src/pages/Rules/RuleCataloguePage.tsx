import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Button,
  PageHeader,
  Table,
  Column,
  Badge,
  Dialog,
  EmptyState,
  Toast,
  ToastItem,
} from '../../components/ui';
import {
  CheckSquare,
  FileText,
  Plus,
  CheckCircle,
  XCircle,
  Loader2,
  Trash2,
  Filter,
} from 'lucide-react';
import { useWorkspace } from '../../context/WorkspaceContext';
import { useAuth } from '../../context/AuthContext';
import { apiFetch } from '../../lib/api';
import { Rule, ApprovedFact } from '../../types';

export const RuleCataloguePage: React.FC<{ initialTab?: 'rules' | 'facts' }> = ({
  initialTab = 'rules',
}) => {
  const { activeWorkspace, isBrandOwner, isAdmin } = useWorkspace();
  const { token } = useAuth();

  const [activeTab, setActiveTab] = useState<'rules' | 'facts'>(initialTab);
  const [rules, setRules] = useState<Rule[]>([]);
  const [facts, setFacts] = useState<ApprovedFact[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Status filters
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Modals
  const [isAddRuleOpen, setIsAddRuleOpen] = useState(false);
  const [isAddFactOpen, setIsAddFactOpen] = useState(false);

  // New Rule Form State
  const [ruleType, setRuleType] = useState<'banned_term' | 'required_wording' | 'terminology'>('banned_term');
  const [ruleSeverity, setRuleSeverity] = useState<'high' | 'medium' | 'low'>('high');
  const [rulePrimaryTerm, setRulePrimaryTerm] = useState('');
  const [ruleSecondaryTerm, setRuleSecondaryTerm] = useState('');
  const [ruleExplanation, setRuleExplanation] = useState('');
  const [isSubmittingRule, setIsSubmittingRule] = useState(false);

  // New Fact Form State
  const [factStatement, setFactStatement] = useState('');
  const [factReference, setFactReference] = useState('');
  const [factOwner, setFactOwner] = useState('Brand Team');
  const [isSubmittingFact, setIsSubmittingFact] = useState(false);

  // Toasts
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = (type: 'success' | 'error' | 'info', message: string) => {
    const id = `toast_${Date.now()}`;
    setToasts((prev) => [...prev, { id, type, message }]);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const canManage = isBrandOwner || isAdmin;

  const fetchKnowledge = useCallback(async () => {
    if (!activeWorkspace || !token) return;
    setIsLoading(true);
    setError(null);
    try {
      const [rulesRes, factsRes] = await Promise.all([
        apiFetch(`/api/v1/workspaces/${activeWorkspace.id}/rules`),
        apiFetch(`/api/v1/workspaces/${activeWorkspace.id}/facts`),
      ]);

      if (!rulesRes.ok || !factsRes.ok) {
        throw new Error('Failed to load rules and facts.');
      }

      const rulesData = await rulesRes.json();
      const factsData = await factsRes.json();

      setRules(rulesData || []);
      setFacts(factsData || []);
    } catch (err: any) {
      setError(err.message || 'Error loading brand knowledge catalogue.');
    } finally {
      setIsLoading(false);
    }
  }, [activeWorkspace, token]);

  useEffect(() => {
    fetchKnowledge();
  }, [fetchKnowledge]);

  const handleUpdateRuleStatus = async (ruleId: string, newStatus: 'confirmed' | 'rejected' | 'retired') => {
    if (!activeWorkspace || !token) return;
    try {
      const res = await apiFetch(`/api/v1/workspaces/${activeWorkspace.id}/rules/${ruleId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: newStatus }),
      });

      if (!res.ok) throw new Error(`Failed to update rule status to ${newStatus}`);
      addToast('success', `Rule marked as ${newStatus}.`);
      await fetchKnowledge();
    } catch (err: any) {
      addToast('error', err.message);
    }
  };

  const handleUpdateFactStatus = async (factId: string, newStatus: 'confirmed' | 'rejected' | 'retired') => {
    if (!activeWorkspace || !token) return;
    try {
      const res = await apiFetch(`/api/v1/workspaces/${activeWorkspace.id}/facts/${factId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: newStatus }),
      });

      if (!res.ok) throw new Error(`Failed to update fact status to ${newStatus}`);
      addToast('success', `Brand fact marked as ${newStatus}.`);
      await fetchKnowledge();
    } catch (err: any) {
      addToast('error', err.message);
    }
  };

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspace || !token) return;
    setIsSubmittingRule(true);

    let payload: Record<string, any> = {};
    if (ruleType === 'banned_term') {
      payload = { banned_term: rulePrimaryTerm.trim(), preferred_term: ruleSecondaryTerm.trim() };
    } else if (ruleType === 'required_wording') {
      payload = { required_term: rulePrimaryTerm.trim(), context: 'compliance' };
    } else {
      payload = { canonical_name: rulePrimaryTerm.trim() };
    }

    try {
      const res = await apiFetch(`/api/v1/workspaces/${activeWorkspace.id}/rules`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          rule_type: ruleType,
          severity: ruleSeverity,
          payload,
          explanation: ruleExplanation.trim(),
        }),
      });

      if (!res.ok) throw new Error('Failed to create rule');
      addToast('success', 'New candidate rule created.');
      setIsAddRuleOpen(false);
      setRulePrimaryTerm('');
      setRuleSecondaryTerm('');
      setRuleExplanation('');
      await fetchKnowledge();
    } catch (err: any) {
      addToast('error', err.message);
    } finally {
      setIsSubmittingRule(false);
    }
  };

  const handleCreateFact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspace || !token) return;
    setIsSubmittingFact(true);

    try {
      const res = await apiFetch(`/api/v1/workspaces/${activeWorkspace.id}/facts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          statement: factStatement.trim(),
          source_reference: factReference.trim(),
          owner: factOwner.trim(),
        }),
      });

      if (!res.ok) throw new Error('Failed to create approved fact');
      addToast('success', 'New candidate fact created.');
      setIsAddFactOpen(false);
      setFactStatement('');
      setFactReference('');
      await fetchKnowledge();
    } catch (err: any) {
      addToast('error', err.message);
    } finally {
      setIsSubmittingFact(false);
    }
  };

  const filteredRules = useMemo(() => {
    if (statusFilter === 'all') return rules;
    return rules.filter((r) => r.status === statusFilter);
  }, [rules, statusFilter]);

  const filteredFacts = useMemo(() => {
    if (statusFilter === 'all') return facts;
    return facts.filter((f) => f.status === statusFilter);
  }, [facts, statusFilter]);

  const ruleColumns: Column<Rule>[] = [
    {
      key: 'rule_type',
      header: 'Rule Type',
      render: (r) => {
        const labels: Record<string, string> = {
          banned_term: 'Banned Term',
          required_wording: 'Required Wording',
          terminology: 'Product Casing',
          tone_attribute: 'Tone',
        };
        return <Badge variant="neutral">{labels[r.rule_type] || r.rule_type}</Badge>;
      },
    },
    {
      key: 'severity',
      header: 'Severity',
      render: (r) => {
        const map: Record<string, 'error' | 'warning' | 'info'> = {
          high: 'error',
          medium: 'warning',
          low: 'info',
        };
        return <Badge variant={map[r.severity] || 'neutral'}>{r.severity.toUpperCase()}</Badge>;
      },
    },
    {
      key: 'explanation',
      header: 'Rule Specification',
      render: (r) => (
        <div className="space-y-1">
          <p className="text-xs font-medium text-surface-900">{r.explanation}</p>
          <div className="text-2xs font-mono text-surface-500">
            {r.rule_type === 'banned_term' && r.payload && (
              <span>
                Avoid: <strong>"{r.payload.banned_term || ''}"</strong>
                {r.payload.preferred_term ? ` → Use: "${r.payload.preferred_term}"` : ''}
              </span>
            )}
            {r.rule_type === 'required_wording' && r.payload && (
              <span>Must include: "{r.payload.required_term || ''}"</span>
            )}
            {r.rule_type === 'terminology' && r.payload && (
              <span>Canonical: "{r.payload.canonical_name || ''}"</span>
            )}
          </div>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Governance Status',
      render: (r) => {
        if (r.status === 'confirmed') return <Badge variant="success">Confirmed Active</Badge>;
        if (r.status === 'candidate') return <Badge variant="warning">Candidate (Unconfirmed)</Badge>;
        if (r.status === 'rejected') return <Badge variant="error">Rejected</Badge>;
        return <Badge variant="neutral">Retired</Badge>;
      },
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      render: (r) =>
        canManage ? (
          <div className="flex items-center justify-end gap-1.5">
            {r.status === 'candidate' && (
              <>
                <Button
                  variant="primary"
                  size="sm"
                  className="text-xs py-1 h-7 bg-emerald-600 hover:bg-emerald-700"
                  leftIcon={<CheckCircle className="h-3 w-3" />}
                  onClick={() => handleUpdateRuleStatus(r.id, 'confirmed')}
                >
                  Confirm
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs py-1 h-7 text-red-600 hover:bg-red-50"
                  leftIcon={<XCircle className="h-3 w-3" />}
                  onClick={() => handleUpdateRuleStatus(r.id, 'rejected')}
                >
                  Reject
                </Button>
              </>
            )}
            {r.status === 'confirmed' && (
              <Button
                variant="ghost"
                size="sm"
                className="text-xs py-1 h-7 text-surface-500 hover:text-red-600 hover:bg-red-50"
                leftIcon={<Trash2 className="h-3 w-3" />}
                onClick={() => handleUpdateRuleStatus(r.id, 'retired')}
              >
                Retire
              </Button>
            )}
          </div>
        ) : null,
    },
  ];

  const factColumns: Column<ApprovedFact>[] = [
    {
      key: 'statement',
      header: 'Approved Statement',
      render: (f) => (
        <span className="text-xs font-medium text-surface-900">{f.statement}</span>
      ),
    },
    {
      key: 'source_reference',
      header: 'Reference Clause',
      render: (f) => <Badge variant="neutral">{f.source_reference}</Badge>,
    },
    {
      key: 'owner',
      header: 'Owner',
      render: (f) => <span className="text-xs text-surface-600">{f.owner}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (f) => {
        if (f.status === 'confirmed') return <Badge variant="success">Confirmed Truth</Badge>;
        if (f.status === 'candidate') return <Badge variant="warning">Candidate Claim</Badge>;
        if (f.status === 'rejected') return <Badge variant="error">Rejected</Badge>;
        return <Badge variant="neutral">Retired</Badge>;
      },
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      render: (f) =>
        canManage ? (
          <div className="flex items-center justify-end gap-1.5">
            {f.status === 'candidate' && (
              <>
                <Button
                  variant="primary"
                  size="sm"
                  className="text-xs py-1 h-7 bg-emerald-600 hover:bg-emerald-700"
                  leftIcon={<CheckCircle className="h-3 w-3" />}
                  onClick={() => handleUpdateFactStatus(f.id, 'confirmed')}
                >
                  Confirm
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs py-1 h-7 text-red-600 hover:bg-red-50"
                  leftIcon={<XCircle className="h-3 w-3" />}
                  onClick={() => handleUpdateFactStatus(f.id, 'rejected')}
                >
                  Reject
                </Button>
              </>
            )}
            {f.status === 'confirmed' && (
              <Button
                variant="ghost"
                size="sm"
                className="text-xs py-1 h-7 text-surface-500 hover:text-red-600 hover:bg-red-50"
                leftIcon={<Trash2 className="h-3 w-3" />}
                onClick={() => handleUpdateFactStatus(f.id, 'retired')}
              >
                Retire
              </Button>
            )}
          </div>
        ) : null,
    },
  ];

  return (
    <div className="space-y-6">
      <Toast toasts={toasts} onDismiss={removeToast} />

      <PageHeader
        title="Brand Knowledge Catalogue"
        description="Active brand rules and verified claims database. Candidate rules remain inactive until confirmed by a Brand Owner."
        actions={
          canManage ? (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                leftIcon={<Plus className="h-4 w-4" />}
                onClick={() => setIsAddFactOpen(true)}
              >
                Add Fact
              </Button>
              <Button
                variant="primary"
                size="sm"
                leftIcon={<Plus className="h-4 w-4" />}
                onClick={() => setIsAddRuleOpen(true)}
              >
                Add Rule
              </Button>
            </div>
          ) : undefined
        }
      />

      {error && (
        <div className="p-3 bg-red-50 text-red-700 text-xs rounded border border-red-200">
          {error}
        </div>
      )}

      {/* Tabs and Filter Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-200 pb-2">
        <div className="flex items-center gap-2">
          <button
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
              activeTab === 'rules'
                ? 'bg-surface-900 text-white'
                : 'text-surface-600 hover:bg-surface-100'
            }`}
            onClick={() => setActiveTab('rules')}
          >
            Brand Rules ({rules.length})
          </button>
          <button
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
              activeTab === 'facts'
                ? 'bg-surface-900 text-white'
                : 'text-surface-600 hover:bg-surface-100'
            }`}
            onClick={() => setActiveTab('facts')}
          >
            Approved Facts ({facts.length})
          </button>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <Filter className="h-3.5 w-3.5 text-surface-400" />
          <span className="text-surface-500">Filter status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs bg-white border border-surface-200 rounded px-2 py-1 text-surface-700"
          >
            <option value="all">All Items</option>
            <option value="candidate">Candidates Only</option>
            <option value="confirmed">Confirmed Active</option>
            <option value="rejected">Rejected</option>
            <option value="retired">Retired</option>
          </select>
        </div>
      </div>

      {/* Content Tables */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center p-12 bg-white rounded-lg border border-surface-200">
          <Loader2 className="h-6 w-6 animate-spin text-surface-500 mb-2" />
          <p className="text-xs text-surface-500">Loading brand knowledge...</p>
        </div>
      ) : activeTab === 'rules' ? (
        filteredRules.length === 0 ? (
          <EmptyState
            icon={<CheckSquare className="h-8 w-8 text-surface-400" />}
            title="No brand rules match filter"
            description="Extract rules automatically from uploaded guidelines or create rules manually."
          />
        ) : (
          <div className="bg-white border border-surface-200 rounded-lg overflow-hidden shadow-sm">
            <Table<Rule> columns={ruleColumns} data={filteredRules} keyExtractor={(r) => r.id} />
          </div>
        )
      ) : filteredFacts.length === 0 ? (
        <EmptyState
          icon={<FileText className="h-8 w-8 text-surface-400" />}
          title="No approved facts match filter"
          description="Build your single source of brand truth with verified statistics, certifications, and claims."
        />
      ) : (
        <div className="bg-white border border-surface-200 rounded-lg overflow-hidden shadow-sm">
          <Table<ApprovedFact>
            columns={factColumns}
            data={filteredFacts}
            keyExtractor={(f) => f.id}
          />
        </div>
      )}

      {/* Add Rule Modal */}
      <Dialog
        isOpen={isAddRuleOpen}
        onClose={() => !isSubmittingRule && setIsAddRuleOpen(false)}
        title="Create Brand Rule"
        maxWidth="md"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsAddRuleOpen(false)}
              disabled={isSubmittingRule}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleCreateRule}
              disabled={!rulePrimaryTerm || !ruleExplanation || isSubmittingRule}
            >
              {isSubmittingRule ? 'Saving...' : 'Save Candidate Rule'}
            </Button>
          </div>
        }
      >
        <form onSubmit={handleCreateRule} className="space-y-4">
          <div>
            <label className="block text-2xs font-semibold text-surface-700 uppercase mb-1">
              Rule Type
            </label>
            <select
              value={ruleType}
              onChange={(e) => setRuleType(e.target.value as any)}
              className="w-full text-xs border border-surface-300 rounded p-2 bg-white"
            >
              <option value="banned_term">Banned Terminology (Prohibited wording)</option>
              <option value="required_wording">Required Wording (Mandatory disclaimer/disclosure)</option>
              <option value="terminology">Product Casing & Spelling</option>
            </select>
          </div>

          <div>
            <label className="block text-2xs font-semibold text-surface-700 uppercase mb-1">
              Severity
            </label>
            <select
              value={ruleSeverity}
              onChange={(e) => setRuleSeverity(e.target.value as any)}
              className="w-full text-xs border border-surface-300 rounded p-2 bg-white"
            >
              <option value="high">High (Blocks approval)</option>
              <option value="medium">Medium (Warning)</option>
              <option value="low">Low (Advisory)</option>
            </select>
          </div>

          <div>
            <label className="block text-2xs font-semibold text-surface-700 uppercase mb-1">
              {ruleType === 'banned_term'
                ? 'Banned Word or Phrase'
                : ruleType === 'required_wording'
                ? 'Mandatory Text'
                : 'Canonical Product Spelling'}
            </label>
            <input
              type="text"
              value={rulePrimaryTerm}
              onChange={(e) => setRulePrimaryTerm(e.target.value)}
              className="w-full text-xs border border-surface-300 rounded p-2"
              placeholder={ruleType === 'banned_term' ? 'e.g. cheap' : 'e.g. AuraHealth'}
              required
            />
          </div>

          {ruleType === 'banned_term' && (
            <div>
              <label className="block text-2xs font-semibold text-surface-700 uppercase mb-1">
                Preferred Replacement (Optional)
              </label>
              <input
                type="text"
                value={ruleSecondaryTerm}
                onChange={(e) => setRuleSecondaryTerm(e.target.value)}
                className="w-full text-xs border border-surface-300 rounded p-2"
                placeholder="e.g. accessible"
              />
            </div>
          )}

          <div>
            <label className="block text-2xs font-semibold text-surface-700 uppercase mb-1">
              Explanation & Rationale
            </label>
            <textarea
              rows={3}
              value={ruleExplanation}
              onChange={(e) => setRuleExplanation(e.target.value)}
              className="w-full text-xs border border-surface-300 rounded p-2"
              placeholder="Why this rule exists according to corporate guidelines..."
              required
            />
          </div>
        </form>
      </Dialog>

      {/* Add Fact Modal */}
      <Dialog
        isOpen={isAddFactOpen}
        onClose={() => !isSubmittingFact && setIsAddFactOpen(false)}
        title="Add Approved Brand Fact"
        maxWidth="md"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsAddFactOpen(false)}
              disabled={isSubmittingFact}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleCreateFact}
              disabled={!factStatement || !factReference || isSubmittingFact}
            >
              {isSubmittingFact ? 'Saving...' : 'Save Candidate Fact'}
            </Button>
          </div>
        }
      >
        <form onSubmit={handleCreateFact} className="space-y-4">
          <div>
            <label className="block text-2xs font-semibold text-surface-700 uppercase mb-1">
              Factual Claim / Statement
            </label>
            <textarea
              rows={3}
              value={factStatement}
              onChange={(e) => setFactStatement(e.target.value)}
              className="w-full text-xs border border-surface-300 rounded p-2"
              placeholder="e.g. Clinically proven in 500 patient trials to improve vitality."
              required
            />
          </div>

          <div>
            <label className="block text-2xs font-semibold text-surface-700 uppercase mb-1">
              Source Reference Clause
            </label>
            <input
              type="text"
              value={factReference}
              onChange={(e) => setFactReference(e.target.value)}
              className="w-full text-xs border border-surface-300 rounded p-2"
              placeholder="e.g. Clinical Study Whitepaper 2026, Section 4"
              required
            />
          </div>

          <div>
            <label className="block text-2xs font-semibold text-surface-700 uppercase mb-1">
              Owner Department
            </label>
            <input
              type="text"
              value={factOwner}
              onChange={(e) => setFactOwner(e.target.value)}
              className="w-full text-xs border border-surface-300 rounded p-2"
              required
            />
          </div>
        </form>
      </Dialog>
    </div>
  );
};
