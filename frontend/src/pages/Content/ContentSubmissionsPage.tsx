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
  FileText,
  Upload,
  Plus,
  Loader2,
  CheckCircle,
  Eye,
} from 'lucide-react';
import { useWorkspace } from '../../context/WorkspaceContext';
import { useAuth } from '../../context/AuthContext';
import { apiFetch } from '../../lib/api';
import { ContentItem, ContentState } from '../../types';

export const ContentSubmissionsPage: React.FC<{
  onSelectContent: (contentId: string) => void;
}> = ({ onSelectContent }) => {
  const { activeWorkspace, isCreator } = useWorkspace();
  const { token } = useAuth();

  const [items, setItems] = useState<ContentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter
  const [filterState, setFilterState] = useState<string>('all');

  // New Submission Modal State
  const [isSubmitOpen, setIsSubmitOpen] = useState(false);
  const [submitMode, setSubmitMode] = useState<'paste' | 'upload'>('paste');
  const [title, setTitle] = useState('');
  const [pastedText, setPastedText] = useState('');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Toasts
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = (type: 'success' | 'error' | 'info', message: string) => {
    const id = `toast_${Date.now()}`;
    setToasts((prev) => [...prev, { id, type, message }]);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const fetchItems = useCallback(async () => {
    if (!activeWorkspace || !token) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/v1/workspaces/${activeWorkspace.id}/content`);
      if (!res.ok) throw new Error('Failed to load content submissions');
      const data = await res.json();
      setItems(data || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [activeWorkspace, token]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  const handleSubmitContent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspace || !token) return;

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      if (submitMode === 'paste') {
        const res = await apiFetch(`/api/v1/workspaces/${activeWorkspace.id}/content`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            title: title.trim(),
            raw_text: pastedText.trim(),
            file_type: 'pasted_text',
          }),
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err?.detail?.message || err?.error?.message || 'Submission failed');
        }

        const created = await res.json();
        addToast('success', `Content '${created.title}' submitted.`);
        setIsSubmitOpen(false);
        setTitle('');
        setPastedText('');
        await fetchItems();
        onSelectContent(created.id);
      } else {
        if (!uploadFile) throw new Error('Please select a PDF or DOCX file to upload');

        const formData = new FormData();
        formData.append('file', uploadFile);

        const res = await apiFetch(
          `/api/v1/workspaces/${activeWorkspace.id}/content/upload?title=${encodeURIComponent(
            title.trim()
          )}`,
          {
            method: 'POST',
            body: formData,
          }
        );

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err?.detail?.message || err?.error?.message || 'File submission failed');
        }

        const created = await res.json();
        addToast('success', `Draft '${created.title}' uploaded and parsed.`);
        setIsSubmitOpen(false);
        setTitle('');
        setUploadFile(null);
        await fetchItems();
        onSelectContent(created.id);
      }
    } catch (err: any) {
      setSubmitError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const getStateBadge = (state: ContentState) => {
    switch (state) {
      case 'draft':
        return <Badge variant="neutral">Draft</Badge>;
      case 'in_review':
        return <Badge variant="info">In Review</Badge>;
      case 'changes_requested':
        return <Badge variant="warning">Changes Requested</Badge>;
      case 'approved':
        return <Badge variant="success">Approved</Badge>;
      default:
        return <Badge variant="neutral">{state}</Badge>;
    }
  };

  const filteredItems = useMemo(() => {
    if (filterState === 'all') return items;
    return items.filter((i) => i.state === filterState);
  }, [items, filterState]);

  const columns: Column<ContentItem>[] = [
    {
      key: 'title',
      header: 'Submission Title',
      render: (i) => (
        <div
          className="flex items-center gap-2 cursor-pointer group"
          onClick={() => onSelectContent(i.id)}
        >
          <FileText className="h-4 w-4 text-surface-500 group-hover:text-surface-900" />
          <span className="font-semibold text-xs text-surface-900 group-hover:underline">
            {i.title}
          </span>
        </div>
      ),
    },
    {
      key: 'file_type',
      header: 'Source Format',
      render: (i) => (
        <Badge variant="neutral">
          {i.file_type === 'pasted_text' ? 'PASTED TEXT' : i.file_type.toUpperCase()}
        </Badge>
      ),
    },
    {
      key: 'current_version',
      header: 'Version',
      render: (i) => (
        <span className="text-xs font-mono font-medium text-surface-600">
          v{i.current_version}
        </span>
      ),
    },
    {
      key: 'state',
      header: 'Governance Status',
      render: (i) => getStateBadge(i.state),
    },
    {
      key: 'created_at',
      header: 'Submitted',
      render: (i) => (
        <span className="text-xs text-surface-500">
          {new Date(i.created_at).toLocaleDateString()}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      render: (i) => (
        <Button
          variant="outline"
          size="sm"
          className="text-xs py-1 h-7"
          leftIcon={<Eye className="h-3 w-3" />}
          onClick={() => onSelectContent(i.id)}
        >
          Open Review
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <Toast toasts={toasts} onDismiss={removeToast} />

      <PageHeader
        title="Marketing Content Submissions"
        description="Submit marketing copy and creative drafts for automated compliance checks, peer review, and manager sign-off."
        actions={
          isCreator ? (
            <Button
              variant="primary"
              size="sm"
              leftIcon={<Plus className="h-4 w-4" />}
              onClick={() => setIsSubmitOpen(true)}
            >
              New Submission
            </Button>
          ) : undefined
        }
      />

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-surface-200 pb-2">
        {['all', 'draft', 'in_review', 'changes_requested', 'approved'].map((st) => (
          <button
            key={st}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors capitalize ${
              filterState === st
                ? 'bg-surface-900 text-white'
                : 'text-surface-600 hover:bg-surface-100'
            }`}
            onClick={() => setFilterState(st)}
          >
            {st.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Main Table */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center p-12 bg-white rounded-lg border border-surface-200">
          <Loader2 className="h-6 w-6 animate-spin text-surface-500 mb-2" />
          <p className="text-xs text-surface-500">Loading submissions...</p>
        </div>
      ) : error ? (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
          {error}
        </div>
      ) : filteredItems.length === 0 ? (
        <EmptyState
          icon={<FileText className="h-8 w-8 text-surface-400" />}
          title="No content submissions found"
          description="Creators can submit marketing copy or upload draft documents to run automated compliance checks."
          action={
            isCreator ? (
              <Button
                variant="primary"
                size="sm"
                leftIcon={<Plus className="h-4 w-4" />}
                onClick={() => setIsSubmitOpen(true)}
              >
                Submit First Draft
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="bg-white border border-surface-200 rounded-lg overflow-hidden shadow-sm">
          <Table<ContentItem>
            columns={columns}
            data={filteredItems}
            keyExtractor={(i) => i.id}
          />
        </div>
      )}

      {/* New Submission Modal */}
      <Dialog
        isOpen={isSubmitOpen}
        onClose={() => !isSubmitting && setIsSubmitOpen(false)}
        title="Submit Content for Review"
        maxWidth="lg"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsSubmitOpen(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSubmitContent}
              disabled={
                !title ||
                (submitMode === 'paste' ? !pastedText : !uploadFile) ||
                isSubmitting
              }
              leftIcon={
                isSubmitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle className="h-4 w-4" />
                )
              }
            >
              {isSubmitting ? 'Submitting...' : 'Submit Draft'}
            </Button>
          </div>
        }
      >
        <form onSubmit={handleSubmitContent} className="space-y-4">
          <div className="flex items-center gap-2 border-b border-surface-200 pb-2">
            <button
              type="button"
              className={`px-3 py-1 text-xs font-semibold rounded ${
                submitMode === 'paste'
                  ? 'bg-surface-800 text-white'
                  : 'text-surface-600 hover:bg-surface-100'
              }`}
              onClick={() => setSubmitMode('paste')}
            >
              Paste Marketing Text
            </button>
            <button
              type="button"
              className={`px-3 py-1 text-xs font-semibold rounded ${
                submitMode === 'upload'
                  ? 'bg-surface-800 text-white'
                  : 'text-surface-600 hover:bg-surface-100'
              }`}
              onClick={() => setSubmitMode('upload')}
            >
              Upload Document (PDF / DOCX)
            </button>
          </div>

          <div>
            <label className="block text-2xs font-semibold text-surface-700 uppercase mb-1">
              Campaign / Submission Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full text-xs border border-surface-300 rounded p-2"
              placeholder="e.g. AuraHealth Q3 Instagram Launch Post"
              required
            />
          </div>

          {submitMode === 'paste' ? (
            <div>
              <label className="block text-2xs font-semibold text-surface-700 uppercase mb-1">
                Content Body (Markdown & Plain Text Supported)
              </label>
              <textarea
                rows={10}
                value={pastedText}
                onChange={(e) => setPastedText(e.target.value)}
                className="w-full text-xs font-mono border border-surface-300 rounded p-3 leading-relaxed"
                placeholder="# Header Title&#10;&#10;Paste marketing copy here..."
                required
              />
            </div>
          ) : (
            <div className="border-2 border-dashed border-surface-300 rounded-lg p-6 text-center hover:border-surface-400 bg-surface-50">
              <input
                type="file"
                id="content-file-upload"
                className="hidden"
                accept=".pdf,.docx"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
              />
              <label
                htmlFor="content-file-upload"
                className="cursor-pointer flex flex-col items-center justify-center gap-2"
              >
                <Upload className="h-8 w-8 text-surface-400" />
                <span className="text-xs font-medium text-surface-700">
                  {uploadFile ? uploadFile.name : 'Choose PDF or Word document'}
                </span>
                <span className="text-2xs text-surface-400">Up to 20MB</span>
              </label>
            </div>
          )}

          {submitError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded text-xs text-red-700">
              {submitError}
            </div>
          )}
        </form>
      </Dialog>
    </div>
  );
};
