-- BrandProof AI: Round 2 Findings and Governance Permissions
-- Forward-only migration granting necessary INSERT/UPDATE permissions and RLS policies on findings and source_passages

-- 1. Source Passages Grants and Policies
GRANT SELECT, INSERT, UPDATE, DELETE ON public.source_passages TO authenticated;

DROP POLICY IF EXISTS source_passages_insert_policy ON public.source_passages;
CREATE POLICY source_passages_insert_policy ON public.source_passages
    FOR INSERT TO authenticated
    WITH CHECK (workspace_id IN (SELECT public.get_user_workspace_ids()));

DROP POLICY IF EXISTS source_passages_update_policy ON public.source_passages;
CREATE POLICY source_passages_update_policy ON public.source_passages
    FOR UPDATE TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()))
    WITH CHECK (workspace_id IN (SELECT public.get_user_workspace_ids()));

DROP POLICY IF EXISTS source_passages_delete_policy ON public.source_passages;
CREATE POLICY source_passages_delete_policy ON public.source_passages
    FOR DELETE TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()));

-- 2. Findings Grants and Policies
GRANT INSERT, UPDATE ON public.findings TO authenticated;

DROP POLICY IF EXISTS findings_insert_policy ON public.findings;
CREATE POLICY findings_insert_policy ON public.findings
    FOR INSERT TO authenticated
    WITH CHECK (workspace_id IN (SELECT public.get_user_workspace_ids()));

DROP POLICY IF EXISTS findings_update_policy ON public.findings;
CREATE POLICY findings_update_policy ON public.findings
    FOR UPDATE TO authenticated
    USING (workspace_id IN (SELECT public.get_user_workspace_ids()))
    WITH CHECK (workspace_id IN (SELECT public.get_user_workspace_ids()));

