-- ==============================================================================
-- BrandProof AI — Phase C, Task 1: Authorization Alignment Forward Migration
-- Enforces:
-- 1. Content submission restricted exclusively to 'creator' role.
-- 2. Content approval restricted exclusively to 'manager' and 'reviewer' roles.
-- 3. Source documents status extended with 'processing', 'processed', 'retired'.
-- ==============================================================================

-- 1. Content Items Insert Policy: strictly creator role
DROP POLICY IF EXISTS content_items_insert_policy ON public.content_items;
CREATE POLICY content_items_insert_policy ON public.content_items
    FOR INSERT TO authenticated
    WITH CHECK (
        workspace_id IN (SELECT public.get_user_workspace_ids('creator'))
        AND created_by = auth.uid()
    );

-- 2. Content Approvals Insert Policy: strictly manager and reviewer roles (denying admin, brand_owner, creator)
DROP POLICY IF EXISTS content_approvals_insert_policy ON public.content_approvals;
CREATE POLICY content_approvals_insert_policy ON public.content_approvals
    FOR INSERT TO authenticated
    WITH CHECK (
        workspace_id IN (SELECT public.get_user_workspace_ids())
        AND (
            public.has_workspace_role(workspace_id, 'manager')
            OR public.has_workspace_role(workspace_id, 'reviewer')
        )
        AND decided_by = auth.uid()
    );

-- 3. Extend Source Documents status constraint to support 'processing', 'processed', and 'retired'
ALTER TABLE public.source_documents DROP CONSTRAINT IF EXISTS source_documents_status_check;
ALTER TABLE public.source_documents ADD CONSTRAINT source_documents_status_check
    CHECK (status IN ('uploaded', 'processing', 'parsing', 'processed', 'extracted', 'failed', 'retired'));

-- 4. Correct lookup_or_create_profile variable shadowing when profile does not exist
CREATE OR REPLACE FUNCTION public.lookup_or_create_profile(p_email TEXT, p_full_name TEXT DEFAULT NULL)
RETURNS TABLE (profile_id UUID, profile_email TEXT, profile_name TEXT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_id UUID;
    v_email TEXT;
    v_name TEXT;
    v_clean_email TEXT;
BEGIN
    v_clean_email := lower(trim(p_email));
    SELECT p.id, p.email, p.full_name INTO v_id, v_email, v_name
    FROM public.profiles p
    WHERE lower(p.email) = v_clean_email;

    IF v_id IS NULL THEN
        v_id := gen_random_uuid();
        v_email := v_clean_email;
        v_name := COALESCE(nullif(trim(p_full_name), ''), split_part(v_clean_email, '@', 1));
        INSERT INTO public.profiles (id, email, full_name)
        VALUES (v_id, v_clean_email, v_name);
    END IF;

    RETURN QUERY SELECT v_id, v_email, v_name;
END;
$$;

ALTER FUNCTION public.lookup_or_create_profile(TEXT, TEXT) OWNER TO postgres;
REVOKE ALL ON FUNCTION public.lookup_or_create_profile(TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.lookup_or_create_profile(TEXT, TEXT) TO authenticated;

