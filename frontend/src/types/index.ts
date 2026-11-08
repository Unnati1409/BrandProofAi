export type UserRole = 'admin' | 'brand_owner' | 'manager' | 'reviewer' | 'creator';

export type ContentState =
  | 'draft'
  | 'checked'
  | 'in_review'
  | 'changes_requested'
  | 'approved'
  | 'archived';

export type FindingSeverity = 'low' | 'medium' | 'high';

export type FindingBasis = 'rule_based' | 'ai_assisted';

export type ClaimVerdict =
  | 'supported'
  | 'contradicted'
  | 'unsupported'
  | 'needs_human_review';

export type TriageIndicator = 'low' | 'medium' | 'high';

export type FindingDecision =
  | 'open'
  | 'applied_suggestion'
  | 'manual_edit'
  | 'dismissed'
  | 'ask_reviewer';

export interface FindingSuggestion {
  id: string;
  original_text: string;
  suggested_text: string;
  recheck_passed: boolean;
}

export interface Finding {
  id: string;
  run_id: string;
  content_version_id: string;
  category: 'terminology' | 'banned_term' | 'required_wording' | 'claim' | 'tone' | 'accessibility';
  severity: FindingSeverity;
  basis_label: FindingBasis;
  start_offset: number;
  end_offset: number;
  paragraph_index?: number;
  page_number?: number;
  rule_id?: string;
  fact_id?: string;
  quoted_submitted_content: string;
  quoted_approved_source: string;
  source_reference: string;
  source_document_name?: string;
  explanation: string;
  verdict?: ClaimVerdict;
  confidence_indicator?: TriageIndicator;
  suggestions: string[];
  accessibility_result?: 'passed' | 'failed' | 'not_checked';
  not_checked_reason?: string;
  decision: FindingDecision;
  decision_reason?: string;
  decided_by?: string;
  decided_at?: string;
  created_at: string;
}

export interface SourcePassage {
  id: string;
  workspace_id: string;
  document_id: string;
  heading?: string | null;
  clause_ref?: string | null;
  passage_text: string;
  page_number?: number | null;
  start_offset?: number | null;
  end_offset?: number | null;
  created_at: string;
}

export interface Rule {
  id: string;
  workspace_id: string;
  rule_type: 'banned_term' | 'required_wording' | 'terminology' | 'tone_attribute';
  severity: FindingSeverity;
  status: 'candidate' | 'confirmed' | 'rejected' | 'retired';
  payload: Record<string, any>;
  explanation: string;
  source_passage_id?: string | null;
  confirmed_by?: string | null;
  confirmed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApprovedFact {
  id: string;
  workspace_id: string;
  statement: string;
  source_reference: string;
  owner: string;
  expiry_date?: string | null;
  status: 'candidate' | 'confirmed' | 'rejected' | 'retired';
  version: number;
  source_passage_id?: string | null;
  confirmed_by?: string | null;
  confirmed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ToneAttribute {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  positive_examples: string[];
  negative_examples: string[];
  status: string;
  created_at: string;
}

export interface ContentItem {
  id: string;
  workspace_id: string;
  title: string;
  file_type: string;
  original_filename?: string | null;
  created_by: string;
  state: ContentState;
  current_version: number;
  created_at: string;
  updated_at: string;
}

export interface ContentVersion {
  id: string;
  content_id: string;
  workspace_id: string;
  version_number: number;
  raw_text: string;
  normalized_text: string;
  parsed_metadata: Record<string, any>;
  created_by: string;
  created_at: string;
}

export interface ContentComment {
  id: string;
  workspace_id: string;
  content_version_id: string;
  finding_id?: string | null;
  author_id: string;
  comment_text: string;
  created_at: string;
}

export interface ContentDetail {
  item: ContentItem;
  versions: ContentVersion[];
  latest_findings: Finding[];
  comments: ContentComment[];
}

export interface ContentExport {
  content_id: string;
  title: string;
  version_number: number;
  state: string;
  content_text: string;
  approval_metadata?: {
    approved_by?: string | null;
    approved_at?: string | null;
    notes?: string | null;
  };
  export_timestamp: string;
  audit_hash: string;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    request_id?: string;
    details?: Array<{ loc?: string[]; msg?: string; type?: string }>;
  };
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  created_by: string;
  ai_enabled: boolean;
  ai_enabled_at?: string | null;
  retention_days: number;
  created_at: string;
}

export interface WorkspaceMember {
  id: string;
  workspace_id: string;
  user_id: string;
  email: string;
  full_name: string;
  roles: UserRole[];
  created_at: string;
}

export interface WorkspaceSettingsUpdate {
  name?: string;
  ai_enabled?: boolean;
  retention_days?: number;
  ai_disclosure_acknowledged?: boolean;
}

export interface SourceDocument {
  id: string;
  workspace_id: string;
  filename: string;
  file_type: string;
  storage_path: string;
  file_size_bytes: number;
  status: 'uploaded' | 'processing' | 'processed' | 'failed' | 'retired';
  error_message?: string | null;
  uploaded_by: string;
  created_at: string;
  is_approved: boolean;
}
