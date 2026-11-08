import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Button,
  Badge,
  Dialog,
  Toast,
  ToastItem,
} from '../../components/ui';
import {
  ArrowLeft,
  Sparkles,
  CheckCircle,
  ShieldCheck,
  Send,
  Download,
  Copy,
  Edit3,
  FileText,
  Loader2,
} from 'lucide-react';
import { useWorkspace } from '../../context/WorkspaceContext';
import { useAuth } from '../../context/AuthContext';
import { apiFetch } from '../../lib/api';
import {
  ContentDetail,
  Finding,
  ContentExport,
} from '../../types';

export const ContentReviewWorkspace: React.FC<{
  contentId: string;
  onBack: () => void;
}> = ({ contentId, onBack }) => {
  const { activeWorkspace, isCreator, isReviewer, isManager } = useWorkspace();
  const { token, user } = useAuth();

  const [detail, setDetail] = useState<ContentDetail | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'findings' | 'comments'>('findings');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Review execution state
  const [isRunningReview, setIsRunningReview] = useState(false);

  // New Version Edit Modal State (for Creator)
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editText, setEditText] = useState('');
  const [isSubmittingVersion, setIsSubmittingVersion] = useState(false);

  // Approval Modal State
  const [isApproveOpen, setIsApproveOpen] = useState(false);
  const [approvalNotes, setApprovalNotes] = useState('');
  const [isApproving, setIsApproving] = useState(false);

  // Request Changes Modal State
  const [isChangesOpen, setIsChangesOpen] = useState(false);
  const [changesNotes, setChangesNotes] = useState('');
  const [isRequestingChanges, setIsRequestingChanges] = useState(false);

  // Dismiss Finding Modal State
  const [dismissFindingTarget, setDismissFindingTarget] = useState<Finding | null>(null);
  const [dismissReason, setDismissReason] = useState('');
  const [isDismissing, setIsDismissing] = useState(false);

  // Export Modal State
  const [exportData, setExportData] = useState<ContentExport | null>(null);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [isLoadingExport, setIsLoadingExport] = useState(false);

  // New Comment Input
  const [newComment, setNewComment] = useState('');
  const [isSubmittingComment, setIsSubmittingComment] = useState(false);

  // Toasts
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = (type: 'success' | 'error' | 'info', message: string) => {
    const id = `toast_${Date.now()}`;
    setToasts((prev) => [...prev, { id, type, message }]);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const fetchDetail = useCallback(async () => {
    if (!activeWorkspace || !token) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/v1/workspaces/${activeWorkspace.id}/content/${contentId}`);
      if (!res.ok) throw new Error('Failed to load content details');
      const data: ContentDetail = await res.json();
      setDetail(data);

      if (!selectedVersionId && data.versions.length > 0) {
        setSelectedVersionId(data.versions[0].id);
        setEditText(data.versions[0].raw_text);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [activeWorkspace, token, contentId, selectedVersionId]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  const activeVersion = useMemo(() => {
    if (!detail) return null;
    return detail.versions.find((v) => v.id === selectedVersionId) || detail.versions[0] || null;
  }, [detail, selectedVersionId]);

  // Execute Review
  const handleRunReview = async () => {
    if (!activeWorkspace || !token) return;
    setIsRunningReview(true);
    try {
      const res = await apiFetch(
        `/api/v1/workspaces/${activeWorkspace.id}/content/${contentId}/review`,
        {
          method: 'POST',
        }
      );

      if (!res.ok) throw new Error('Review execution failed');
      const findings = await res.json();
      addToast(
        'success',
        `Review complete. ${findings.length} findings recorded.`
      );
      await fetchDetail();
    } catch (err: any) {
      addToast('error', err.message);
    } finally {
      setIsRunningReview(false);
    }
  };

  // Submit New Version (Creator edits copy)
  const handleSubmitNewVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspace || !token) return;
    setIsSubmittingVersion(true);
    try {
      const res = await apiFetch(
        `/api/v1/workspaces/${activeWorkspace.id}/content/${contentId}/versions`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ raw_text: editText.trim() }),
        }
      );

      if (!res.ok) throw new Error('Failed to submit updated version');
      const newVer = await res.json();
      addToast('success', `Version ${newVer.version_number} submitted.`);
      setIsEditOpen(false);
      setSelectedVersionId(newVer.id);
      await fetchDetail();
    } catch (err: any) {
      addToast('error', err.message);
    } finally {
      setIsSubmittingVersion(false);
    }
  };

  // Resolve Finding
  const handleResolveFinding = async (finding: Finding, decision: 'applied_suggestion' | 'manual_edit') => {
    if (!activeWorkspace || !token) return;
    try {
      const res = await apiFetch(
        `/api/v1/workspaces/${activeWorkspace.id}/content/findings/${finding.id}`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            decision,
            decision_reason: 'Resolved during creator revision.',
          }),
        }
      );

      if (!res.ok) throw new Error('Failed to update finding decision');
      addToast('success', 'Finding marked as resolved.');
      await fetchDetail();
    } catch (err: any) {
      addToast('error', err.message);
    }
  };

  // Dismiss Finding
  const handleDismissFinding = async () => {
    if (!dismissFindingTarget || !activeWorkspace || !token) return;
    setIsDismissing(true);
    try {
      const res = await apiFetch(
        `/api/v1/workspaces/${activeWorkspace.id}/content/findings/${dismissFindingTarget.id}`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            decision: 'dismissed',
            decision_reason: dismissReason.trim(),
          }),
        }
      );

      if (!res.ok) throw new Error('Failed to dismiss finding');
      addToast('info', 'Finding dismissed with reason.');
      setDismissFindingTarget(null);
      setDismissReason('');
      await fetchDetail();
    } catch (err: any) {
      addToast('error', err.message);
    } finally {
      setIsDismissing(false);
    }
  };

  // Approve Content
  const handleApproveContent = async () => {
    if (!activeWorkspace || !token) return;
    setIsApproving(true);
    try {
      const res = await apiFetch(
        `/api/v1/workspaces/${activeWorkspace.id}/content/${contentId}/approve`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            decision: 'approved',
            notes: approvalNotes.trim() || undefined,
          }),
        }
      );

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail?.message || err?.error?.message || 'Approval failed');
      }

      addToast('success', 'Content successfully approved for publishing.');
      setIsApproveOpen(false);
      await fetchDetail();
    } catch (err: any) {
      addToast('error', err.message);
    } finally {
      setIsApproving(false);
    }
  };

  // Request Changes
  const handleRequestChanges = async () => {
    if (!activeWorkspace || !token) return;
    setIsRequestingChanges(true);
    try {
      const res = await apiFetch(
        `/api/v1/workspaces/${activeWorkspace.id}/content/${contentId}/approve`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            decision: 'changes_requested',
            notes: changesNotes.trim(),
          }),
        }
      );

      if (!res.ok) throw new Error('Failed to request changes');
      addToast('info', 'Changes requested. Creator notified.');
      setIsChangesOpen(false);
      await fetchDetail();
    } catch (err: any) {
      addToast('error', err.message);
    } finally {
      setIsRequestingChanges(false);
    }
  };

  // Export Content
  const handleExportContent = async () => {
    if (!activeWorkspace || !token) return;
    setIsLoadingExport(true);
    try {
      const res = await apiFetch(
        `/api/v1/workspaces/${activeWorkspace.id}/content/${contentId}/export`
      );

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail?.message || err?.error?.message || 'Export failed');
      }

      const data: ContentExport = await res.json();
      setExportData(data);
      setIsExportOpen(true);
    } catch (err: any) {
      addToast('error', err.message);
    } finally {
      setIsLoadingExport(false);
    }
  };

  // Post Comment
  const handlePostComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspace || !token || !activeVersion || !newComment.trim()) return;
    setIsSubmittingComment(true);
    try {
      const res = await apiFetch(
        `/api/v1/workspaces/${activeWorkspace.id}/content/${contentId}/comments`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            content_version_id: activeVersion.id,
            comment_text: newComment.trim(),
          }),
        }
      );

      if (!res.ok) throw new Error('Failed to post comment');
      setNewComment('');
      await fetchDetail();
    } catch (err: any) {
      addToast('error', err.message);
    } finally {
      setIsSubmittingComment(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-16 text-surface-500">
        <Loader2 className="h-6 w-6 animate-spin mb-2" />
        <p className="text-xs">Loading review workspace...</p>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 space-y-3">
        <p>{error || 'Content not found'}</p>
        <Button variant="outline" size="sm" onClick={onBack}>
          Back to Submissions
        </Button>
      </div>
    );
  }

  const { item, latest_findings, comments } = detail;
  const isCreatorOfContent = item.created_by === user?.id;
  const canApproveAction = (isReviewer || isManager) && !isCreatorOfContent;

  return (
    <div className="space-y-4">
      <Toast toasts={toasts} onDismiss={removeToast} />

      {/* Header Bar */}
      <div className="bg-white border border-surface-200 rounded-lg p-4 shadow-sm space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <button
              onClick={onBack}
              className="p-1.5 rounded hover:bg-surface-100 text-surface-600 transition-colors"
              title="Back"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-sm font-bold text-surface-900">{item.title}</h1>
                <Badge
                  variant={
                    item.state === 'approved'
                      ? 'success'
                      : item.state === 'in_review'
                      ? 'info'
                      : item.state === 'changes_requested'
                      ? 'warning'
                      : 'neutral'
                  }
                >
                  {item.state.replace('_', ' ').toUpperCase()}
                </Badge>
              </div>
              <p className="text-2xs text-surface-500">
                Format: {item.file_type} • Created {new Date(item.created_at).toLocaleString()}
              </p>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              leftIcon={
                isRunningReview ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Sparkles className="h-3 w-3 text-amber-500" />
                )
              }
              onClick={handleRunReview}
              disabled={isRunningReview}
            >
              {isRunningReview ? 'Auditing...' : 'Run Review'}
            </Button>

            {isCreator && (
              <Button
                variant="outline"
                size="sm"
                leftIcon={<Edit3 className="h-3 w-3 text-surface-600" />}
                onClick={() => {
                  setEditText(activeVersion?.raw_text || '');
                  setIsEditOpen(true);
                }}
              >
                Edit Copy
              </Button>
            )}

            {(isReviewer || isManager) && item.state !== 'approved' && (
              <Button
                variant="outline"
                size="sm"
                className="text-amber-700 hover:bg-amber-50"
                onClick={() => setIsChangesOpen(true)}
              >
                Request Changes
              </Button>
            )}

            {canApproveAction && item.state !== 'approved' && (
              <Button
                variant="primary"
                size="sm"
                className="bg-emerald-600 hover:bg-emerald-700"
                leftIcon={<CheckCircle className="h-3 w-3" />}
                onClick={() => setIsApproveOpen(true)}
              >
                Approve Content
              </Button>
            )}

            {isCreatorOfContent && (isReviewer || isManager) && item.state !== 'approved' && (
              <div
                className="text-2xs font-mono text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded"
                title="Separation of duties invariant"
              >
                Creator Self-Approval Prohibited
              </div>
            )}

            {item.state === 'approved' && (
              <Button
                variant="primary"
                size="sm"
                className="bg-surface-900"
                leftIcon={
                  isLoadingExport ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Download className="h-3 w-3" />
                  )
                }
                onClick={handleExportContent}
                disabled={isLoadingExport}
              >
                Export Approved Copy
              </Button>
            )}
          </div>
        </div>

        {/* Version Selector */}
        <div className="flex items-center gap-2 pt-2 border-t border-surface-100 text-xs">
          <span className="text-surface-500 font-medium">Viewing Version:</span>
          <div className="flex items-center gap-1">
            {detail.versions.map((v) => (
              <button
                key={v.id}
                onClick={() => setSelectedVersionId(v.id)}
                className={`px-2 py-0.5 rounded text-2xs font-mono font-medium transition-colors ${
                  activeVersion?.id === v.id
                    ? 'bg-surface-900 text-white'
                    : 'bg-surface-100 text-surface-600 hover:bg-surface-200'
                }`}
              >
                v{v.version_number}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Review Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Submitted Text Viewer */}
        <div className="lg:col-span-7 bg-white border border-surface-200 rounded-lg p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between border-b border-surface-100 pb-2">
            <span className="text-xs font-bold text-surface-900 uppercase tracking-wider flex items-center gap-2">
              <FileText className="h-4 w-4 text-surface-500" />
              Content Draft (v{activeVersion?.version_number})
            </span>
            <span className="text-2xs text-surface-400 font-mono">
              {activeVersion?.raw_text.length || 0} characters
            </span>
          </div>

          <div className="p-4 bg-surface-50 rounded-lg border border-surface-200/80 font-mono text-xs text-surface-800 whitespace-pre-wrap leading-relaxed min-h-[420px]">
            {activeVersion?.raw_text}
          </div>
        </div>

        {/* Right Column: Findings & Comments Tabs */}
        <div className="lg:col-span-5 bg-white border border-surface-200 rounded-lg p-5 shadow-sm space-y-4">
          <div className="flex items-center gap-2 border-b border-surface-100 pb-2">
            <button
              onClick={() => setActiveTab('findings')}
              className={`px-3 py-1 text-xs font-semibold rounded transition-colors ${
                activeTab === 'findings'
                  ? 'bg-surface-900 text-white'
                  : 'text-surface-600 hover:bg-surface-100'
              }`}
            >
              Findings ({latest_findings.length})
            </button>
            <button
              onClick={() => setActiveTab('comments')}
              className={`px-3 py-1 text-xs font-semibold rounded transition-colors ${
                activeTab === 'comments'
                  ? 'bg-surface-900 text-white'
                  : 'text-surface-600 hover:bg-surface-100'
              }`}
            >
              Comments ({comments.length})
            </button>
          </div>

          {activeTab === 'findings' ? (
            latest_findings.length === 0 ? (
              <div className="p-8 text-center text-xs text-emerald-700 bg-emerald-50/50 border border-emerald-200 rounded-lg space-y-2">
                <CheckCircle className="h-6 w-6 text-emerald-600 mx-auto" />
                <p className="font-semibold">Zero Policy Violations Found</p>
                <p className="text-2xs text-emerald-600">
                  Content conforms to all confirmed brand rules and accessibility checks.
                </p>
              </div>
            ) : (
              <div className="space-y-3.5 max-h-[550px] overflow-y-auto pr-1">
                {latest_findings.map((f) => (
                  <div
                    key={f.id}
                    className={`border rounded-lg p-3.5 space-y-2.5 transition-colors ${
                      f.decision === 'applied_suggestion' || f.decision === 'manual_edit'
                        ? 'border-emerald-200 bg-emerald-50/30'
                        : f.decision === 'dismissed'
                        ? 'border-surface-200 bg-surface-50 opacity-60'
                        : f.severity === 'high'
                        ? 'border-red-200 bg-red-50/30'
                        : 'border-amber-200 bg-amber-50/30'
                    }`}
                  >
                    <div className="flex items-center justify-between text-2xs">
                      <div className="flex items-center gap-1.5">
                        <Badge
                          variant={
                            f.severity === 'high'
                              ? 'error'
                              : f.severity === 'medium'
                              ? 'warning'
                              : 'neutral'
                          }
                        >
                          {f.severity.toUpperCase()}
                        </Badge>
                        <Badge variant="neutral">{f.category.replace('_', ' ')}</Badge>
                      </div>
                      <Badge
                        variant={
                          f.verdict === 'contradicted'
                            ? 'error'
                            : f.verdict === 'unsupported'
                            ? 'warning'
                            : 'neutral'
                        }
                      >
                        {f.verdict || f.basis_label}
                      </Badge>
                    </div>

                    <p className="text-xs font-medium text-surface-900">{f.explanation}</p>

                    <div className="space-y-1.5 text-2xs bg-white p-2.5 rounded border border-surface-200">
                      <div>
                        <span className="text-surface-400 font-semibold uppercase block">
                          Submitted Text:
                        </span>
                        <span className="font-mono text-red-700 bg-red-50 px-1 py-0.5 rounded inline-block mt-0.5">
                          "{f.quoted_submitted_content}"
                        </span>
                      </div>
                      <div>
                        <span className="text-surface-400 font-semibold uppercase block mt-1">
                          Approved Source Authority:
                        </span>
                        <span className="font-mono text-emerald-800 bg-emerald-50 px-1 py-0.5 rounded inline-block mt-0.5">
                          {f.quoted_approved_source}
                        </span>
                      </div>
                      {f.suggestions.length > 0 && (
                        <div>
                          <span className="text-surface-400 font-semibold uppercase block mt-1">
                            Suggested Revision:
                          </span>
                          <span className="font-mono text-primary-700 bg-primary-50 px-1 py-0.5 rounded inline-block mt-0.5">
                            {f.suggestions[0]}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Resolution Actions */}
                    <div className="flex items-center justify-between pt-1">
                      <span className="text-2xs font-mono text-surface-500">
                        Status: <strong>{f.decision.replace('_', ' ')}</strong>
                      </span>
                      {f.decision === 'open' && (
                        <div className="flex items-center gap-1.5">
                          <Button
                            variant="primary"
                            size="sm"
                            className="text-2xs py-0.5 h-6 bg-emerald-600 hover:bg-emerald-700"
                            onClick={() => handleResolveFinding(f, 'applied_suggestion')}
                          >
                            Resolve
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-2xs py-0.5 h-6 text-surface-500 hover:text-red-600"
                            onClick={() => setDismissFindingTarget(f)}
                          >
                            Dismiss
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )
          ) : (
            <div className="space-y-4">
              <div className="space-y-2.5 max-h-[380px] overflow-y-auto pr-1">
                {comments.length === 0 ? (
                  <p className="text-2xs text-surface-400 text-center py-8">
                    No reviewer comments yet.
                  </p>
                ) : (
                  comments.map((c) => (
                    <div
                      key={c.id}
                      className="p-3 bg-surface-50 rounded-lg border border-surface-200 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between text-2xs text-surface-500">
                        <span className="font-semibold text-surface-700">Reviewer Note</span>
                        <span>{new Date(c.created_at).toLocaleTimeString()}</span>
                      </div>
                      <p className="text-surface-800 leading-relaxed">{c.comment_text}</p>
                    </div>
                  ))
                )}
              </div>

              <form onSubmit={handlePostComment} className="space-y-2 pt-2 border-t border-surface-100">
                <textarea
                  rows={2}
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                  placeholder="Leave review note or requested correction..."
                  className="w-full text-xs border border-surface-300 rounded p-2 focus:ring-1 focus:ring-surface-900"
                />
                <div className="flex justify-end">
                  <Button
                    variant="primary"
                    size="sm"
                    className="text-xs h-7 py-0.5"
                    disabled={!newComment.trim() || isSubmittingComment}
                    leftIcon={<Send className="h-3 w-3" />}
                  >
                    Post Comment
                  </Button>
                </div>
              </form>
            </div>
          )}
        </div>
      </div>

      {/* Edit Copy Modal (Creator) */}
      <Dialog
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
        title="Edit Content Copy (Create New Version)"
        maxWidth="lg"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setIsEditOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSubmitNewVersion}
              disabled={!editText.trim() || isSubmittingVersion}
            >
              {isSubmittingVersion ? 'Submitting...' : 'Save & Submit Version'}
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          <p className="text-xs text-surface-600">
            Applying edits creates a new version (v{(detail.versions[0]?.version_number || 1) + 1})
            and sets the status to In Review.
          </p>
          <textarea
            rows={12}
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            className="w-full font-mono text-xs border border-surface-300 rounded p-3 leading-relaxed"
          />
        </div>
      </Dialog>

      {/* Approve Modal */}
      <Dialog
        isOpen={isApproveOpen}
        onClose={() => setIsApproveOpen(false)}
        title="Approve Content for Publishing"
        maxWidth="sm"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setIsApproveOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              className="bg-emerald-600 hover:bg-emerald-700"
              onClick={handleApproveContent}
              disabled={isApproving}
            >
              {isApproving ? 'Approving...' : 'Confirm Approval'}
            </Button>
          </div>
        }
      >
        <div className="space-y-3 text-xs">
          <p className="text-surface-700 leading-relaxed">
            You are signing off on this content draft as a Reviewer / Manager. This records a
            permanent approval entry in the audit trail.
          </p>
          <textarea
            rows={2}
            value={approvalNotes}
            onChange={(e) => setApprovalNotes(e.target.value)}
            placeholder="Approval sign-off notes (optional)..."
            className="w-full text-xs border border-surface-300 rounded p-2"
          />
        </div>
      </Dialog>

      {/* Request Changes Modal */}
      <Dialog
        isOpen={isChangesOpen}
        onClose={() => setIsChangesOpen(false)}
        title="Request Changes"
        maxWidth="sm"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setIsChangesOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              className="bg-amber-600 hover:bg-amber-700"
              onClick={handleRequestChanges}
              disabled={!changesNotes.trim() || isRequestingChanges}
            >
              {isRequestingChanges ? 'Submitting...' : 'Send Changes Request'}
            </Button>
          </div>
        }
      >
        <div className="space-y-3 text-xs">
          <p className="text-surface-700">Specify why changes are needed before approval:</p>
          <textarea
            rows={3}
            value={changesNotes}
            onChange={(e) => setChangesNotes(e.target.value)}
            placeholder="Feedback for creator..."
            className="w-full text-xs border border-surface-300 rounded p-2"
            required
          />
        </div>
      </Dialog>

      {/* Dismiss Finding Modal */}
      <Dialog
        isOpen={Boolean(dismissFindingTarget)}
        onClose={() => setDismissFindingTarget(null)}
        title="Dismiss Finding with Reason"
        maxWidth="sm"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setDismissFindingTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDismissFinding}
              disabled={!dismissReason.trim() || isDismissing}
            >
              {isDismissing ? 'Dismissing...' : 'Dismiss Finding'}
            </Button>
          </div>
        }
      >
        <div className="space-y-3 text-xs">
          <p className="text-surface-700">
            Provide a compliance rationale for dismissing this finding:
          </p>
          <textarea
            rows={2}
            value={dismissReason}
            onChange={(e) => setDismissReason(e.target.value)}
            placeholder="e.g. Legal exception granted for this campaign..."
            className="w-full text-xs border border-surface-300 rounded p-2"
            required
          />
        </div>
      </Dialog>

      {/* Export Dialog */}
      <Dialog
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        title="Approved Content Export Certificate"
        maxWidth="lg"
        footer={
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (exportData) {
                navigator.clipboard.writeText(exportData.content_text);
                addToast('success', 'Content copied to clipboard.');
              }
            }}
            leftIcon={<Copy className="h-4 w-4" />}
          >
            Copy Approved Copy
          </Button>
        }
      >
        {exportData && (
          <div className="space-y-4 text-xs">
            <div className="bg-emerald-50 border border-emerald-200 rounded p-3 space-y-1">
              <div className="flex items-center gap-2 text-emerald-800 font-semibold">
                <ShieldCheck className="h-4 w-4 text-emerald-600" />
                Verified Approved Brand Copy
              </div>
              <p className="text-2xs text-emerald-700 font-mono">
                SHA-256 Audit Hash: {exportData.audit_hash}
              </p>
              <p className="text-2xs text-emerald-700">
                Export Timestamp: {new Date(exportData.export_timestamp).toLocaleString()}
              </p>
            </div>

            <div>
              <span className="block text-2xs font-semibold text-surface-500 uppercase mb-1">
                Final Approved Body
              </span>
              <pre className="p-3 bg-surface-50 rounded border border-surface-200 font-mono text-xs whitespace-pre-wrap">
                {exportData.content_text}
              </pre>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
};
