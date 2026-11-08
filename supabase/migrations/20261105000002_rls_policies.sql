-- ==============================================================================
-- BrandProof AI — Row Level Security (RLS) Policies Migration
-- Migration: 20261105000002_rls_policies.sql
-- Description: Enforces multi-tenant data isolation at the PostgreSQL engine level.
-- ==============================================================================

-- 1. Helper function to check workspace membership via auth.uid()
CREATE OR REPLACE FUNCTION is_workspace_member(ws_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM workspace_members
        WHERE workspace_id = ws_id AND user_id = auth.uid()
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 2. Helper function to check specific role in workspace
CREATE OR REPLACE FUNCTION has_workspace_role(ws_id UUID, required_role TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM workspace_members
        WHERE workspace_id = ws_id
          AND user_id = auth.uid()
          AND required_role = ANY(roles)
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ==============================================================================
-- ENABLE RLS ON ALL TABLES
-- ==============================================================================
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_passages ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalogue_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE approved_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE tone_attributes ENABLE ROW LEVEL SECURITY;
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- ==============================================================================
-- PROFILES POLICIES
-- ==============================================================================
CREATE POLICY profiles_select_policy ON profiles
    FOR SELECT TO authenticated
    USING (
        id = auth.uid() OR
        EXISTS (
            SELECT 1 FROM workspace_members wm1
            JOIN workspace_members wm2 ON wm1.workspace_id = wm2.workspace_id
            WHERE wm1.user_id = auth.uid() AND wm2.user_id = profiles.id
        )
    );

CREATE POLICY profiles_update_policy ON profiles
    FOR UPDATE TO authenticated
    USING (id = auth.uid());

-- ==============================================================================
-- WORKSPACES POLICIES
-- ==============================================================================
CREATE POLICY workspaces_select_policy ON workspaces
    FOR SELECT TO authenticated
    USING (is_workspace_member(id) OR created_by = auth.uid());

CREATE POLICY workspaces_insert_policy ON workspaces
    FOR INSERT TO authenticated
    WITH CHECK (created_by = auth.uid());

CREATE POLICY workspaces_update_policy ON workspaces
    FOR UPDATE TO authenticated
    USING (has_workspace_role(id, 'admin'));

CREATE POLICY workspaces_delete_policy ON workspaces
    FOR DELETE TO authenticated
    USING (has_workspace_role(id, 'admin'));

-- ==============================================================================
-- WORKSPACE MEMBERS POLICIES
-- ==============================================================================
CREATE POLICY members_select_policy ON workspace_members
    FOR SELECT TO authenticated
    USING (is_workspace_member(workspace_id));

CREATE POLICY members_insert_policy ON workspace_members
    FOR INSERT TO authenticated
    WITH CHECK (has_workspace_role(workspace_id, 'admin') OR user_id = auth.uid());

CREATE POLICY members_update_policy ON workspace_members
    FOR UPDATE TO authenticated
    USING (has_workspace_role(workspace_id, 'admin'));

CREATE POLICY members_delete_policy ON workspace_members
    FOR DELETE TO authenticated
    USING (has_workspace_role(workspace_id, 'admin') OR user_id = auth.uid());

-- ==============================================================================
-- WORKSPACE RESOURCE ISOLATION (Standard Tenant Scoping)
-- ==============================================================================

-- Source Documents & Passages
CREATE POLICY source_documents_policy ON source_documents
    FOR ALL TO authenticated
    USING (is_workspace_member(workspace_id))
    WITH CHECK (is_workspace_member(workspace_id));

CREATE POLICY source_passages_policy ON source_passages
    FOR ALL TO authenticated
    USING (is_workspace_member(workspace_id))
    WITH CHECK (is_workspace_member(workspace_id));

-- Catalogue Versions, Rules & Facts
CREATE POLICY catalogue_versions_policy ON catalogue_versions
    FOR ALL TO authenticated
    USING (is_workspace_member(workspace_id))
    WITH CHECK (is_workspace_member(workspace_id));

CREATE POLICY rules_policy ON rules
    FOR ALL TO authenticated
    USING (is_workspace_member(workspace_id))
    WITH CHECK (is_workspace_member(workspace_id));

CREATE POLICY approved_facts_policy ON approved_facts
    FOR ALL TO authenticated
    USING (is_workspace_member(workspace_id))
    WITH CHECK (is_workspace_member(workspace_id));

CREATE POLICY tone_attributes_policy ON tone_attributes
    FOR ALL TO authenticated
    USING (is_workspace_member(workspace_id))
    WITH CHECK (is_workspace_member(workspace_id));

CREATE POLICY assets_policy ON assets
    FOR ALL TO authenticated
    USING (is_workspace_member(workspace_id))
    WITH CHECK (is_workspace_member(workspace_id));

-- Content Items & Versions
CREATE POLICY content_items_policy ON content_items
    FOR ALL TO authenticated
    USING (is_workspace_member(workspace_id))
    WITH CHECK (is_workspace_member(workspace_id));

CREATE POLICY content_versions_policy ON content_versions
    FOR ALL TO authenticated
    USING (is_workspace_member(workspace_id))
    WITH CHECK (is_workspace_member(workspace_id));

-- Review Runs & Findings
CREATE POLICY review_runs_policy ON review_runs
    FOR ALL TO authenticated
    USING (is_workspace_member(workspace_id))
    WITH CHECK (is_workspace_member(workspace_id));

CREATE POLICY findings_policy ON findings
    FOR ALL TO authenticated
    USING (is_workspace_member(workspace_id))
    WITH CHECK (is_workspace_member(workspace_id));

CREATE POLICY content_comments_policy ON content_comments
    FOR ALL TO authenticated
    USING (is_workspace_member(workspace_id))
    WITH CHECK (is_workspace_member(workspace_id));

CREATE POLICY content_approvals_policy ON content_approvals
    FOR ALL TO authenticated
    USING (is_workspace_member(workspace_id))
    WITH CHECK (is_workspace_member(workspace_id));

-- Audit Logs (Append-Only read/insert)
CREATE POLICY audit_logs_select_policy ON audit_logs
    FOR SELECT TO authenticated
    USING (is_workspace_member(workspace_id) AND (has_workspace_role(workspace_id, 'admin') OR has_workspace_role(workspace_id, 'manager')));

CREATE POLICY audit_logs_insert_policy ON audit_logs
    FOR INSERT TO authenticated
    WITH CHECK (is_workspace_member(workspace_id));

