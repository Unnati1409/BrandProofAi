-- ==============================================================================
-- BrandProof AI — Core Database Schema Migration
-- Migration: 20261105000001_core_schema.sql
-- Description: Establishes extensions, relational tables, constraints, triggers,
--              creator self-approval prevention, and audit immutability.
-- ==============================================================================

-- 1. Enable Required PostgreSQL Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS "vector";
EXCEPTION WHEN OTHERS THEN
    NULL;
END $$;

-- 2. Profiles Table (Mirrors Supabase Auth Users)
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Workspaces Table
CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    created_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    ai_enabled BOOLEAN NOT NULL DEFAULT false,
    ai_enabled_at TIMESTAMPTZ,
    ai_enabled_by UUID REFERENCES profiles(id),
    retention_days INTEGER NOT NULL DEFAULT 90,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Workspace Members Table (Multi-role support per user)
CREATE TABLE IF NOT EXISTS workspace_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    roles TEXT[] NOT NULL DEFAULT '{"creator"}',
    invited_by UUID REFERENCES profiles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_workspace_member UNIQUE (workspace_id, user_id)
);

-- 5. Source Documents (Uploaded brand guidelines PDF / DOCX)
CREATE TABLE IF NOT EXISTS source_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL CHECK (file_type IN ('pdf', 'docx')),
    storage_path TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'parsing', 'extracted', 'failed')),
    error_message TEXT,
    uploaded_by UUID NOT NULL REFERENCES profiles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 6. Source Passages (Segmented clauses with pgvector embeddings)
CREATE TABLE IF NOT EXISTS source_passages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    heading TEXT,
    clause_ref TEXT,
    passage_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    page_number INTEGER,
    start_offset INTEGER,
    end_offset INTEGER,
    embedding vector(768),
    embedding_model TEXT,
    embedding_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 7. Catalogue Versions (Immutable snapshots of confirmed brand knowledge)
CREATE TABLE IF NOT EXISTS catalogue_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    change_summary TEXT NOT NULL,
    created_by UUID NOT NULL REFERENCES profiles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_workspace_catalogue_version UNIQUE (workspace_id, version_number)
);

-- 8. Rules Table (Terminology, banned terms, required wording, tone)
CREATE TABLE IF NOT EXISTS rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    catalogue_version_id UUID REFERENCES catalogue_versions(id) ON DELETE SET NULL,
    source_passage_id UUID REFERENCES source_passages(id) ON DELETE SET NULL,
    rule_type TEXT NOT NULL CHECK (rule_type IN ('terminology', 'banned_term', 'required_wording', 'tone_attribute', 'palette_accessibility')),
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
    status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate', 'confirmed', 'rejected', 'retired')),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    explanation TEXT NOT NULL,
    confirmed_by UUID REFERENCES profiles(id),
    confirmed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 9. Approved Fact Base
CREATE TABLE IF NOT EXISTS approved_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    catalogue_version_id UUID REFERENCES catalogue_versions(id) ON DELETE SET NULL,
    source_passage_id UUID REFERENCES source_passages(id) ON DELETE SET NULL,
    statement TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    owner TEXT NOT NULL,
    expiry_date DATE,
    status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate', 'confirmed', 'rejected', 'retired')),
    embedding vector(768),
    embedding_model TEXT,
    embedding_version TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    confirmed_by UUID REFERENCES profiles(id),
    confirmed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 10. Tone Attributes (Feature-flagged, built last)
CREATE TABLE IF NOT EXISTS tone_attributes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    positive_examples TEXT[] NOT NULL DEFAULT '{}',
    negative_examples TEXT[] NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate', 'confirmed', 'retired')),
    embedding vector(768),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 11. Assets (Palette hex codes & reference logos)
CREATE TABLE IF NOT EXISTS assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('palette_color', 'logo_file', 'reference_file')),
    name TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    storage_path TEXT,
    created_by UUID NOT NULL REFERENCES profiles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 12. Content Items (Submissions undergoing governance)
CREATE TABLE IF NOT EXISTS content_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    original_filename TEXT,
    file_type TEXT NOT NULL CHECK (file_type IN ('pasted_text', 'docx', 'pdf')),
    created_by UUID NOT NULL REFERENCES profiles(id),
    state TEXT NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'checked', 'in_review', 'changes_requested', 'approved', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 13. Content Versions (Word-level snapshots of drafts)
CREATE TABLE IF NOT EXISTS content_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    content_id UUID NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    parsed_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by UUID NOT NULL REFERENCES profiles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_content_version UNIQUE (content_id, version_number)
);

-- 14. Review Runs (Evaluations executed on a specific content version)
CREATE TABLE IF NOT EXISTS review_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    content_version_id UUID NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
    catalogue_version_id UUID REFERENCES catalogue_versions(id) ON DELETE SET NULL,
    model_identifier TEXT,
    prompt_version TEXT,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'complete', 'failed')),
    failure_reason TEXT,
    timings_ms JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by UUID NOT NULL REFERENCES profiles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- 15. Findings Table
CREATE TABLE IF NOT EXISTS findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    run_id UUID NOT NULL REFERENCES review_runs(id) ON DELETE CASCADE,
    content_version_id UUID NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
    category TEXT NOT NULL CHECK (category IN ('terminology', 'banned_term', 'required_wording', 'claim', 'tone', 'accessibility')),
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
    basis_label TEXT NOT NULL CHECK (basis_label IN ('rule_based', 'ai_assisted')),
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    paragraph_index INTEGER,
    page_number INTEGER,
    rule_id UUID REFERENCES rules(id) ON DELETE SET NULL,
    fact_id UUID REFERENCES approved_facts(id) ON DELETE SET NULL,
    quoted_submitted_content TEXT NOT NULL,
    quoted_approved_source TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    source_document_name TEXT,
    explanation TEXT NOT NULL,
    verdict TEXT CHECK (verdict IN ('supported', 'contradicted', 'unsupported', 'needs_human_review')),
    confidence_indicator TEXT CHECK (confidence_indicator IN ('low', 'medium', 'high')),
    suggestions JSONB NOT NULL DEFAULT '[]'::jsonb,
    accessibility_result TEXT CHECK (accessibility_result IN ('passed', 'failed', 'not_checked')),
    not_checked_reason TEXT,
    decision TEXT NOT NULL DEFAULT 'open' CHECK (decision IN ('open', 'applied_suggestion', 'manual_edit', 'dismissed', 'ask_reviewer')),
    decision_reason TEXT,
    decided_by UUID REFERENCES profiles(id),
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 16. Content Comments
CREATE TABLE IF NOT EXISTS content_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    content_version_id UUID NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
    finding_id UUID REFERENCES findings(id) ON DELETE CASCADE,
    author_id UUID NOT NULL REFERENCES profiles(id),
    comment_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 17. Content Approvals Table
CREATE TABLE IF NOT EXISTS content_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    content_id UUID NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    content_version_id UUID NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'changes_requested')),
    notes TEXT,
    decided_by UUID NOT NULL REFERENCES profiles(id),
    decided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ==============================================================================
-- DATABASE LEVEL CONSTRAINT: CREATOR CANNOT APPROVE OWN CONTENT
-- ==============================================================================
CREATE OR REPLACE FUNCTION check_creator_not_approver()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM content_items
        WHERE id = NEW.content_id AND created_by = NEW.decided_by
    ) THEN
        RAISE EXCEPTION 'Creator cannot approve their own content (content_id: %, approver_id: %)',
            NEW.content_id, NEW.decided_by
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_creator_cannot_approve ON content_approvals;
CREATE TRIGGER trg_creator_cannot_approve
BEFORE INSERT OR UPDATE ON content_approvals
FOR EACH ROW
EXECUTE FUNCTION check_creator_not_approver();

-- 18. Append-Only Audit Logs Table
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    actor_id UUID REFERENCES profiles(id),
    event_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- IMMUTABILITY: Revoke UPDATE and DELETE on audit_logs from all non-superuser roles
REVOKE UPDATE, DELETE ON audit_logs FROM authenticated, anon, public;

-- ==============================================================================
-- INDEXES FOR PERFORMANCE AND RETRIEVAL
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_workspace_members_lookup ON workspace_members(user_id, workspace_id);
CREATE INDEX IF NOT EXISTS idx_rules_workspace_status ON rules(workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_facts_workspace_status ON approved_facts(workspace_id, status, expiry_date);
CREATE INDEX IF NOT EXISTS idx_content_workspace_state ON content_items(workspace_id, state);
CREATE INDEX IF NOT EXISTS idx_findings_version_severity ON findings(content_version_id, severity, decision);
CREATE INDEX IF NOT EXISTS idx_audit_workspace_created ON audit_logs(workspace_id, created_at DESC);

