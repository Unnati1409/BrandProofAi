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
  Upload,
  FileText,
  AlertTriangle,
  ShieldAlert,
  Loader2,
  Trash2,
  FileCheck,
  Sparkles,
  Eye,
} from 'lucide-react';
import { useWorkspace } from '../../context/WorkspaceContext';
import { useAuth } from '../../context/AuthContext';
import { apiFetch } from '../../lib/api';
import { SourceDocument, SourcePassage } from '../../types';

export const GuidelinesPage: React.FC = () => {
  const { activeWorkspace, isBrandOwner, isAdmin } = useWorkspace();
  const { token } = useAuth();

  const [sources, setSources] = useState<SourceDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Upload dialog state
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Retire dialog state
  const [retireTarget, setRetireTarget] = useState<SourceDocument | null>(null);
  const [isRetiring, setIsRetiring] = useState(false);

  // Processing state
  const [processingId, setProcessingId] = useState<string | null>(null);

  // Passages viewer state
  const [viewingPassagesDoc, setViewingPassagesDoc] = useState<SourceDocument | null>(null);
  const [passages, setPassages] = useState<SourcePassage[]>([]);
  const [isLoadingPassages, setIsLoadingPassages] = useState(false);

  // Toasts
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = (type: 'success' | 'error' | 'info', message: string) => {
    const id = `toast_${Date.now()}`;
    setToasts((prev) => [...prev, { id, type, message }]);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const canManageSources = isBrandOwner || isAdmin;

  const fetchSources = useCallback(async () => {
    if (!activeWorkspace || !token) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/v1/workspaces/${activeWorkspace.id}/sources`);
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson?.error?.message || 'Failed to fetch guideline sources.');
      }
      const data = await res.json();
      setSources(data.items || []);
    } catch (err: any) {
      setError(err.message || 'An error occurred while loading guideline sources.');
    } finally {
      setIsLoading(false);
    }
  }, [activeWorkspace, token]);

  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUploadError(null);
    const file = e.target.files?.[0];
    if (!file) return;

    const lower = file.name.toLowerCase();
    if (!lower.endsWith('.pdf') && !lower.endsWith('.docx')) {
      setUploadError('Only .pdf and .docx documents are accepted.');
      setSelectedFile(null);
      return;
    }

    if (file.size > 20 * 1024 * 1024) {
      setUploadError('File size exceeds the 20MB limit.');
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || !activeWorkspace || !token) return;

    setIsUploading(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const res = await apiFetch(`/api/v1/workspaces/${activeWorkspace.id}/sources/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson?.detail?.message || errJson?.error?.message || 'Upload failed.');
      }

      addToast('success', `Guideline '${selectedFile.name}' imported as Candidate Source.`);
      setIsUploadOpen(false);
      setSelectedFile(null);
      await fetchSources();
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload document.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleProcessDocument = async (doc: SourceDocument) => {
    if (!activeWorkspace || !token) return;
    setProcessingId(doc.id);

    try {
      const res = await apiFetch(`/api/v1/workspaces/${activeWorkspace.id}/sources/${doc.id}/process`, {
        method: 'POST',
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson?.detail?.message || errJson?.error?.message || 'Processing failed.');
      }

      const result = await res.json();
      addToast(
        'success',
        `Extracted ${result.passages_count} passages, ${result.candidate_rules_extracted} candidate rules, and ${result.candidate_facts_extracted} candidate facts.`
      );
      await fetchSources();
    } catch (err: any) {
      addToast('error', err.message || 'Failed to process guideline.');
    } finally {
      setProcessingId(null);
    }
  };

  const handleViewPassages = async (doc: SourceDocument) => {
    if (!activeWorkspace || !token) return;
    setViewingPassagesDoc(doc);
    setIsLoadingPassages(true);

    try {
      const res = await apiFetch(`/api/v1/workspaces/${activeWorkspace.id}/sources/${doc.id}/passages`);
      if (!res.ok) throw new Error('Failed to load passages');
      const data = await res.json();
      setPassages(data || []);
    } catch (err: any) {
      addToast('error', err.message || 'Could not load passages');
    } finally {
      setIsLoadingPassages(false);
    }
  };

  const handleRetireSubmit = async () => {
    if (!retireTarget || !activeWorkspace || !token) return;

    setIsRetiring(true);
    try {
      const res = await apiFetch(
        `/api/v1/workspaces/${activeWorkspace.id}/sources/${retireTarget.id}`,
        {
          method: 'DELETE',
        }
      );

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson?.error?.message || 'Failed to retire source document.');
      }

      addToast('info', `Guideline '${retireTarget.filename}' retired.`);
      setRetireTarget(null);
      await fetchSources();
    } catch (err: any) {
      addToast('error', err.message || 'An error occurred while retiring the document.');
    } finally {
      setIsRetiring(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'uploaded':
        return <Badge variant="warning">Uploaded (Pending Extraction)</Badge>;
      case 'processing':
        return <Badge variant="info">Processing Clauses</Badge>;
      case 'processed':
        return <Badge variant="success">Extracted Clauses</Badge>;
      case 'failed':
        return <Badge variant="error">Extraction Failed</Badge>;
      case 'retired':
        return <Badge variant="neutral">Retired</Badge>;
      default:
        return <Badge variant="neutral">{status}</Badge>;
    }
  };

  // Table Columns Definition
  const columns: Column<SourceDocument>[] = useMemo(() => {
    const baseCols: Column<SourceDocument>[] = [
      {
        key: 'filename',
        header: 'Document Name',
        render: (item) => (
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-surface-500 flex-shrink-0" />
            <span className="font-medium text-surface-900 text-xs">{item.filename}</span>
          </div>
        ),
      },
      {
        key: 'file_type',
        header: 'Format',
        render: (item) => <Badge variant="neutral">{item.file_type.toUpperCase()}</Badge>,
      },
      {
        key: 'file_size_bytes',
        header: 'Size',
        render: (item) => (
          <span className="text-xs text-surface-500">{formatFileSize(item.file_size_bytes)}</span>
        ),
      },
      {
        key: 'status',
        header: 'Processing Status',
        render: (item) => getStatusBadge(item.status),
      },
      {
        key: 'governance_status',
        header: 'Governance Status',
        render: (item) =>
          item.status === 'retired' ? (
            <Badge variant="neutral">Not In Use</Badge>
          ) : (
            <Badge variant="warning">Unapproved Candidate</Badge>
          ),
      },
      {
        key: 'created_at',
        header: 'Uploaded Date',
        render: (item) => (
          <span className="text-xs text-surface-500">
            {new Date(item.created_at).toLocaleDateString()}
          </span>
        ),
      },
      {
        key: 'actions',
        header: 'Actions',
        align: 'right',
        render: (item) => (
          <div className="flex items-center justify-end gap-1.5">
            {item.status !== 'retired' && (
              <>
                {(item.status === 'uploaded' || item.status === 'failed') && canManageSources && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs py-1 h-7"
                    leftIcon={
                      processingId === item.id ? (
                        <Loader2 className="h-3 w-3 animate-spin text-surface-600" />
                      ) : (
                        <Sparkles className="h-3 w-3 text-amber-500" />
                      )
                    }
                    disabled={processingId === item.id}
                    onClick={() => handleProcessDocument(item)}
                  >
                    {processingId === item.id ? 'Processing...' : 'Process Document'}
                  </Button>
                )}

                {item.status === 'processed' && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs py-1 h-7 text-surface-700"
                    leftIcon={<Eye className="h-3 w-3" />}
                    onClick={() => handleViewPassages(item)}
                  >
                    View Passages
                  </Button>
                )}

                {canManageSources && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-600 hover:text-red-700 hover:bg-red-50 text-xs py-1 h-7"
                    leftIcon={<Trash2 className="h-3 w-3" />}
                    onClick={() => setRetireTarget(item)}
                  >
                    Retire
                  </Button>
                )}
              </>
            )}
            {item.status === 'retired' && (
              <span className="text-2xs text-surface-400 font-mono">Archived</span>
            )}
          </div>
        ),
      },
    ];

    return baseCols;
  }, [canManageSources, processingId]);

  return (
    <div className="space-y-6">
      <Toast toasts={toasts} onDismiss={removeToast} />

      <PageHeader
        title="Guideline Source Management"
        description="Import corporate brand books, clinical claims schedules, and regulatory rules to build the evidence base."
        actions={
          canManageSources ? (
            <Button
              variant="primary"
              size="sm"
              leftIcon={<Upload className="h-4 w-4" />}
              onClick={() => setIsUploadOpen(true)}
            >
              Upload Guideline
            </Button>
          ) : undefined
        }
      />

      {/* Candidate Invariant Callout */}
      <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-4">
        <div className="flex items-start gap-3">
          <ShieldAlert className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-amber-900 leading-relaxed">
            <span className="font-semibold block mb-0.5">
              Approval Invariant: Raw Documents Are Candidate Evidence
            </span>
            Imported guidelines remain <strong>Unapproved Candidates</strong>. Clicking{' '}
            <strong>Process Document</strong> extracts verifiable passages and generates candidate
            rules and facts. No rule or fact is used as active compliance authority until explicitly
            confirmed by a Brand Owner.
          </div>
        </div>
      </div>

      {/* Main Table */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center p-12 bg-white rounded-lg border border-surface-200">
          <Loader2 className="h-6 w-6 animate-spin text-surface-500 mb-2" />
          <p className="text-xs text-surface-500">Loading guideline documents...</p>
        </div>
      ) : error ? (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3 text-xs text-red-800">
          <AlertTriangle className="h-4 w-4 text-red-600 flex-shrink-0" />
          <span>{error}</span>
        </div>
      ) : sources.length === 0 ? (
        <EmptyState
          icon={<FileText className="h-8 w-8 text-surface-400" />}
          title="No guideline documents imported"
          description="Upload your official brand voice books, legal disclaimers, and claims matrices to begin automated compliance governance."
          action={
            canManageSources ? (
              <Button
                variant="primary"
                size="sm"
                leftIcon={<Upload className="h-4 w-4" />}
                onClick={() => setIsUploadOpen(true)}
              >
                Upload First Guideline
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="bg-white border border-surface-200 rounded-lg overflow-hidden shadow-sm">
          <Table<SourceDocument>
            columns={columns}
            data={sources}
            keyExtractor={(item) => item.id}
          />
        </div>
      )}

      {/* Upload Modal Dialog */}
      <Dialog
        isOpen={isUploadOpen}
        onClose={() => !isUploading && setIsUploadOpen(false)}
        title="Import Brand Guideline"
        maxWidth="md"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsUploadOpen(false)}
              disabled={isUploading}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleUploadSubmit}
              disabled={!selectedFile || isUploading}
              leftIcon={
                isUploading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="h-4 w-4" />
                )
              }
            >
              {isUploading ? 'Validating & Uploading...' : 'Upload Guideline'}
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          <p className="text-xs text-surface-600 leading-relaxed">
            Upload an official PDF or Word (.docx) brand specification. The document will be
            verified with binary magic-byte inspection and stored in workspace-isolated storage.
          </p>

          <div className="border-2 border-dashed border-surface-300 rounded-lg p-6 text-center hover:border-surface-400 transition-colors bg-surface-50/50">
            <input
              type="file"
              id="guideline-file-input"
              className="hidden"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={handleFileChange}
              disabled={isUploading}
            />
            <label
              htmlFor="guideline-file-input"
              className="cursor-pointer flex flex-col items-center justify-center gap-2"
            >
              <Upload className="h-8 w-8 text-surface-400" />
              <div className="text-xs font-medium text-surface-700">
                {selectedFile ? (
                  <span className="text-primary-600 font-semibold">{selectedFile.name}</span>
                ) : (
                  <span>Click to select or drag and drop</span>
                )}
              </div>
              <p className="text-2xs text-surface-400">PDF or DOCX (up to 20MB)</p>
            </label>
          </div>

          {selectedFile && (
            <div className="flex items-center gap-2 p-2 bg-surface-100 rounded text-xs text-surface-700">
              <FileCheck className="h-4 w-4 text-emerald-600 flex-shrink-0" />
              <span className="truncate flex-1 font-mono text-2xs">{selectedFile.name}</span>
              <span className="text-2xs text-surface-500 font-mono">
                {formatFileSize(selectedFile.size)}
              </span>
            </div>
          )}

          {uploadError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded text-xs text-red-700 flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
              <span>{uploadError}</span>
            </div>
          )}
        </div>
      </Dialog>

      {/* Passages Viewer Dialog */}
      <Dialog
        isOpen={Boolean(viewingPassagesDoc)}
        onClose={() => setViewingPassagesDoc(null)}
        title={viewingPassagesDoc ? `Passages: ${viewingPassagesDoc.filename}` : 'Extracted Passages'}
        maxWidth="lg"
      >
        <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
          {isLoadingPassages ? (
            <div className="flex flex-col items-center justify-center p-8 text-surface-500">
              <Loader2 className="h-6 w-6 animate-spin mb-2" />
              <span className="text-xs">Loading structured passages...</span>
            </div>
          ) : passages.length === 0 ? (
            <div className="p-8 text-center text-xs text-surface-500">
              No passages found for this document.
            </div>
          ) : (
            passages.map((p, idx) => (
              <div
                key={p.id || idx}
                className="border border-surface-200 rounded-lg p-3.5 bg-surface-50/50 space-y-1.5"
              >
                <div className="flex items-center justify-between text-2xs text-surface-500">
                  <span className="font-semibold text-surface-800">
                    {p.heading || `Clause ${idx + 1}`}
                  </span>
                  <Badge variant="neutral">
                    {p.clause_ref || (p.page_number ? `Page ${p.page_number}` : 'Section')}
                  </Badge>
                </div>
                <p className="text-xs text-surface-700 leading-relaxed font-mono bg-white p-2.5 rounded border border-surface-100">
                  {p.passage_text}
                </p>
              </div>
            ))
          )}
        </div>
      </Dialog>

      {/* Retire Confirmation Dialog */}
      <Dialog
        isOpen={Boolean(retireTarget)}
        onClose={() => !isRetiring && setRetireTarget(null)}
        title="Retire Guideline Source"
        maxWidth="sm"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setRetireTarget(null)}
              disabled={isRetiring}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleRetireSubmit}
              disabled={isRetiring}
              leftIcon={
                isRetiring ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4" />
                )
              }
            >
              {isRetiring ? 'Retiring...' : 'Confirm Retire'}
            </Button>
          </div>
        }
      >
        <p className="text-xs text-surface-600 leading-relaxed">
          Are you sure you want to retire <strong>{retireTarget?.filename}</strong>? Once retired,
          this document and clauses extracted from it will no longer be referenced in compliance
          audits. Existing audit logs will remain preserved.
        </p>
      </Dialog>
    </div>
  );
};
